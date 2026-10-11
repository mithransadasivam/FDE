"""Thumbs up and down: validated, saved as numbers and file names only, the question only when the person opts in."""
import json

import pytest

from app.feedback import (FeedbackError, MAX_QUESTION_CHARS_SAVED, REASONS, build_entry, clean_question, read_feedback, record_feedback, summarize, to_csv)


def save(path, rating="up", reason="", **kwargs):
    return record_feedback(rating, kwargs.pop("outcome", "answered"), kwargs.pop("best_score", 0.8), kwargs.pop("chunks_used", 4),
                           kwargs.pop("sources", ["vpn.md"]), reason, path=path, **kwargs)


def test_a_rating_is_saved_as_one_json_line_with_numbers_and_file_names_only(tmp_path):
    path = tmp_path / "f.jsonl"
    record = save(path, "down", "Wrong source", sources=["b.md", "a.pdf", "a.pdf"], best_score=0.71234)
    line = json.loads(path.read_text(encoding="utf-8").strip())
    assert line == record and set(line) == {"time", "rating", "reason", "outcome", "best_score", "chunks_used", "sources"}
    assert line["sources"] == ["a.pdf", "b.md"] and line["best_score"] == 0.712 and line["rating"] == "down" and line["reason"] == "Wrong source"


def test_the_answer_is_never_saved_and_the_question_only_when_asked_for(tmp_path):
    path = tmp_path / "f.jsonl"
    save(path, "down", "Other", question="My password is hunter2, why is VPN slow?")                       # not opted in
    save(path, "down", "Other", question="Why is VPN slow?", include_question=True)                          # opted in
    rows = read_feedback(path)
    assert "question" not in rows[0] and "hunter2" not in path.read_text(encoding="utf-8")
    assert rows[1]["question"] == "Why is VPN slow?"
    assert "answer" not in rows[0] and "answer" not in rows[1]


def test_an_opted_in_question_is_cleaned_and_shortened():
    assert clean_question("  a\x00b\n\n  c\t d ") == "a b c d"
    assert len(clean_question("x" * 1000)) == MAX_QUESTION_CHARS_SAVED
    assert "question" not in build_entry("down", "answered", 0.5, 4, [], "Other", question="   ", include_question=True)


@pytest.mark.parametrize("rating,reason", [("sideways", ""), ("", ""), ("up", "Wrong source"), ("down", "free text reason"), ("down", "wrong source")])
def test_a_bad_rating_or_reason_is_refused(tmp_path, rating, reason):
    with pytest.raises(FeedbackError):
        save(tmp_path / "f.jsonl", rating, reason)
    assert not (tmp_path / "f.jsonl").exists()


def test_every_listed_reason_is_accepted_for_a_thumbs_down(tmp_path):
    for reason in REASONS:
        assert save(tmp_path / "f.jsonl", "down", reason)["reason"] == reason
    assert save(tmp_path / "f.jsonl", "down", "")["reason"] == ""  # a thumbs down with no reason is fine


def test_odd_values_are_made_safe():
    entry = build_entry("up", "something else", "n/a", "many", ["x" * 500] + [f"f{n}.md" for n in range(20)])
    assert entry["outcome"] == "answered" and entry["best_score"] is None and entry["chunks_used"] == 0 and len(entry["sources"]) == 6
    assert all(len(s) <= 80 for s in entry["sources"])


def test_a_write_problem_never_breaks_the_chatbot(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    assert save(blocker / "inside" / "f.jsonl", "up")["rating"] == "up"  # the folder cannot be made: ignored


def test_the_tests_never_write_to_the_real_feedback_log():
    from app import feedback
    assert feedback.ENABLED is False
    record_feedback("up", "answered", 0.9, 4, ["a.md"])  # no path given: must write nothing, and must not raise


def test_unreadable_lines_are_skipped_and_the_summary_counts_the_thumbs_down(tmp_path):
    path = tmp_path / "f.jsonl"
    save(path, "up")
    save(path, "down", "Wrong source", sources=["vpn.md"], outcome="answered")
    save(path, "down", "Should have answered", sources=[], outcome="declined", question="q", include_question=True)
    save(path, "down", "Wrong source", sources=["vpn.md", "mfa.md"])
    with open(path, "a", encoding="utf-8") as f:
        f.write("not json\n[1,2]\n" + json.dumps({"rating": "meh"}) + "\n")
    summary = summarize(read_feedback(path))
    assert summary["total"] == 4 and summary["up"] == 1 and summary["down"] == 3 and summary["down_rate"] == 0.75
    assert summary["by_reason"] == {"Wrong source": 2, "Should have answered": 1} and summary["by_outcome"] == {"answered": 2, "declined": 1}
    assert summary["files"][0] == ("vpn.md", 2) and summary["with_question"] == 1


def test_an_empty_log_is_an_empty_summary(tmp_path):
    assert read_feedback(tmp_path / "nothing.jsonl") == []
    assert summarize([])["total"] == 0 and summarize([])["down_rate"] is None


def test_the_csv_has_only_the_thumbs_down_and_neutralises_formulas(tmp_path):
    path = tmp_path / "f.jsonl"
    save(path, "up")
    save(path, "down", "Other", question="=HYPERLINK(\"http://evil\")", include_question=True)
    text = to_csv(read_feedback(path))
    lines = text.strip().splitlines()
    assert lines[0] == "time,reason,outcome,best_score,sources,question" and len(lines) == 2
    assert "'=HYPERLINK" in lines[1] and ",=HYPERLINK" not in lines[1]
