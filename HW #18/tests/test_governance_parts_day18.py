"""Day 18: tests for the finished parts. They pass from the start, before any TODO is done."""

import json

from app.evidence import SOURCES, collect, fingerprint
from app.fairness import (
    ask_as,
    judge_tone,
    load_profiles,
    load_questions,
    numbers,
    summarise,
)
from app.model_card import empty, render_markdown


def test_the_class_data_is_complete():
    profiles, questions = load_profiles(), load_questions()
    assert (
        profiles[0]["id"] == "baseline" and len(profiles) == 5 and len(questions) == 5
    )
    assert all(q["question"] and q["second_language"] for q in questions)
    with open("data/Day18_Slide09_use_cases.json", encoding="utf-8") as f:
        assert [c["id"] for c in json.load(f)] == ["UC-01", "UC-02", "UC-03", "UC-04"]


def test_questions_are_asked_as_each_person():
    q = {
        "question": "How long can a VPN session stay connected?",
        "second_language": "how long VPN stay?",
    }
    assert ask_as({"intro": ""}, q) == q["question"]
    assert (
        ask_as({"intro": "Hi, I'm Kwame."}, q)
        == "Hi, I'm Kwame. How long can a VPN session stay connected?"
    )
    assert (
        ask_as({"intro": "Hello.", "use_variant": True}, q)
        == "Hello. how long VPN stay?"
    )


def test_numbers_ignore_citations():
    assert numbers("12 hours [1], then 15 minutes [2]") == {"12", "15"}


def test_the_judge_reads_json_and_the_fake_compares_texts(monkeypatch):
    class Client:
        def __init__(self, text):
            msg = type("M", (), {"content": text})()
            reply = type("R", (), {"choices": [type("C", (), {"message": msg})()]})()
            self.chat = type(
                "Ch",
                (),
                {"completions": type("Co", (), {"create": lambda s, **k: reply})()},
            )()

    monkeypatch.setenv("CHAT_FAKE", "0")
    assert judge_tone(
        "a",
        "b",
        client=Client('{"same_treatment": false, "reason": "curt"}'),
        model="m",
    ) == {"same_treatment": False, "reason": "curt"}
    assert (
        judge_tone("a", "b", client=Client("no json"), model="m")["same_treatment"]
        is False
    )
    monkeypatch.setenv("CHAT_FAKE", "1")
    assert judge_tone("same", "same")["same_treatment"] is True


def test_the_summary_counts_answers_per_profile():
    rows = [{"profile": "p", "differences": []}, {"profile": "p", "differences": ["x"]}]
    assert summarise(rows) == {"p": {"answers": 2, "differed": 1, "rate": 0.5}}


def test_evidence_is_copied_with_a_manifest(tmp_path):
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "bias_report.json").write_text('{"summary": {}}')
    r = collect(root=str(tmp_path), today="2026-10-19")
    assert r["copied"] == ["bias_report.json"] and len(r["missing"]) == len(SOURCES) - 1
    copied = tmp_path / "governance" / "evidence" / "bias_report.json"
    manifest = (tmp_path / "governance" / "evidence" / "MANIFEST.md").read_text()
    assert (
        copied.exists() and fingerprint(copied) in manifest and "2026-10-19" in manifest
    )


def test_the_model_card_page_lists_its_gaps():
    page = render_markdown(
        {
            "name": "Bot",
            "evaluation": [{"metric": "m", "value": "1", "source": "s"}],
            "limitations": ["a"],
        },
        ["missing: purpose"],
    )
    assert (
        page.startswith("# Model card: Bot")
        and "| m | 1 | s |" in page
        and "- missing: purpose" in page
    )
    assert empty("TODO later") and empty([]) and empty("  ") and not empty("ok")
