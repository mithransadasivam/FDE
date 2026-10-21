import pytest

from app.evaluate import load_questions, load_runs, next_run_number, run_tests, save_run, summarize

QUESTIONS = [
    {"question": "q1", "expected": "e1", "should_answer": True},
    {"question": "q2", "expected": "e2", "should_answer": True},
    {"question": "q3", "expected": "e3", "should_answer": False},
    {"question": "q4", "expected": "e4", "should_answer": False},
]


def fake_answer(declined_questions):
    def fn(question):
        declined = question in declined_questions
        return {
            "answer": "no" if declined else "yes [1]",
            "sources": [] if declined else [{"number": 1, "source": "a.md", "page": 2}],
            "declined": declined, "best_score": 0.7, "seconds": 2.0, "reason": "",
        }
    return fn


def test_load_questions_reads_csv(tmp_path):
    f = tmp_path / "q.csv"
    f.write_text("question,expected_answer,should_answer\nHow?,Like this,yes\nWhy?,Not covered,no\n", encoding="utf-8")
    qs = load_questions(f)
    assert qs == [
        {"question": "How?", "expected": "Like this", "should_answer": True},
        {"question": "Why?", "expected": "Not covered", "should_answer": False},
    ]


def test_load_questions_rejects_bad_flag(tmp_path):
    f = tmp_path / "q.csv"
    f.write_text("question,expected_answer,should_answer\nHow?,x,maybe\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_questions(f)


def test_behaviour_scoring_and_summary():
    # q2 is wrongly declined, q4 is wrongly answered
    rows = run_tests(QUESTIONS, fake_answer({"q2", "q3"}))
    assert [r["ok"] for r in rows] == [True, False, True, False]
    s = summarize(rows)
    assert (s["behaviour_correct"], s["answered_correctly"], s["declined_correctly"]) == (2, 1, 1)
    assert s["total"] == 4 and s["should_answer"] == 2 and s["should_decline"] == 2
    assert s["avg_seconds"] == 2.0
    assert rows[0]["sources"] == "[1] a.md p.2" and rows[1]["sources"] == ""


def test_error_is_recorded_and_run_continues():
    def flaky(question):
        if question == "q1":
            raise RuntimeError("boom")
        return fake_answer(set())(question)

    rows = run_tests(QUESTIONS, flaky)
    assert rows[0]["behaviour"] == "error" and not rows[0]["ok"] and "RuntimeError" in rows[0]["reason"]
    assert len(rows) == 4 and rows[1]["behaviour"] == "answered"


def test_pause_between_questions_only():
    waits = []
    run_tests(QUESTIONS, fake_answer(set()), pause=3, sleep=waits.append)
    assert waits == [3, 3, 3]


def test_save_and_load_runs_number_sequentially(tmp_path):
    rows = run_tests(QUESTIONS, fake_answer(set()))
    first = save_run(rows, 0.55, tmp_path, note="baseline")
    second = save_run(rows, 0.6, tmp_path)
    assert (first["run"], second["run"]) == (1, 2) and next_run_number(tmp_path) == 3
    runs = load_runs(tmp_path)
    assert [r["run"] for r in runs] == [1, 2] and runs[0]["min_score"] == 0.55 and runs[0]["note"] == "baseline"
    assert (tmp_path / "run_1.csv").exists()


def test_load_runs_empty_or_missing_folder(tmp_path):
    assert load_runs(tmp_path / "nothing") == []


# ---- security hardening (Phase 8 review) ----
import csv
import json

from app.evaluate import _csv_safe


def test_oddly_named_result_files_are_ignored(tmp_path):
    rows = run_tests(QUESTIONS, fake_answer(set()))
    save_run(rows, 0.55, tmp_path)
    for name in ("run_final.json", "run_.json", "run_\u00b2.json", "run_1.json.bak", "run_x_2.json"):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    assert [r["run"] for r in load_runs(tmp_path)] == [1]
    assert next_run_number(tmp_path) == 2


def test_incomplete_or_broken_run_files_are_skipped(tmp_path):
    rows = run_tests(QUESTIONS, fake_answer(set()))
    save_run(rows, 0.55, tmp_path)
    (tmp_path / "run_2.json").write_text(json.dumps({"run": 2}), encoding="utf-8")        # missing keys
    (tmp_path / "run_3.json").write_text("not json at all", encoding="utf-8")              # corrupt
    (tmp_path / "run_4.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")         # wrong shape
    assert [r["run"] for r in load_runs(tmp_path)] == [1]


def test_csv_cells_cannot_run_as_formulas(tmp_path):
    assert _csv_safe('=HYPERLINK("https://evil.example","click")').startswith("'=")
    assert _csv_safe("+1") == "'+1" and _csv_safe("-2") == "'-2" and _csv_safe("@x") == "'@x"
    assert _csv_safe("normal text") == "normal text" and _csv_safe(5) == 5

    def evil(question):
        return {"answer": '=HYPERLINK("https://evil.example","click")', "sources": [], "declined": False,
                "best_score": 0.7, "seconds": 1.0, "reason": ""}

    run = save_run(run_tests(QUESTIONS[:1], evil), 0.55, tmp_path)
    with open(tmp_path / f"run_{run['run']}.csv", newline="", encoding="utf-8") as f:
        cell = next(csv.DictReader(f))["answer"]
    assert cell.startswith("'=")
