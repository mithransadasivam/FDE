"""Day 18, Activity 2: compare_answers() finds where another user's answer differs from the baseline."""

from app.fairness import compare_answers, load_profiles, load_questions, run_bias_test

BASE = {
    "answer": "A VPN session can stay connected for a maximum of 12 hours [1].",
    "sources": ["vpn.pdf, page 1"],
    "declined": False,
}
NO = {
    "answer": "I don't know: the documents don't cover that.",
    "sources": [],
    "declined": True,
}


def test_the_same_answer_has_no_differences():
    assert compare_answers(BASE, dict(BASE)) == []


def test_a_refusal_for_one_user_only_is_the_only_difference_reported():
    assert compare_answers(BASE, NO) == ["declined differently"]
    assert compare_answers(NO, BASE) == ["declined differently"]
    assert compare_answers(NO, dict(NO)) == []


def test_different_sources_and_numbers():
    other = {
        "answer": "A VPN session can stay connected for 8 hours [2].",
        "sources": ["old.pdf, page 3"],
        "declined": False,
    }
    assert compare_answers(BASE, other) == ["different sources", "different numbers"]


def test_citation_markers_are_not_numbers():
    other = {
        **BASE,
        "answer": "A VPN session can stay connected for a maximum of 12 hours [2].",
    }
    assert compare_answers(BASE, other) == []


def test_much_shorter_and_much_longer():
    short = {**BASE, "answer": "12 hours [1]."}
    long = {
        **BASE,
        "answer": BASE["answer"] + " After 12 hours you must sign in again, " * 3,
    }
    assert compare_answers(BASE, short) == ["much shorter"]
    assert compare_answers(BASE, long) == ["much longer"]


def test_the_bias_test_finds_the_second_language_refusal(fake_chatbot, monkeypatch):
    from app import service

    monkeypatch.setenv("CACHE", "0")
    monkeypatch.delenv("GUARDRAILS", raising=False)
    rows = run_bias_test(load_questions(), load_profiles(), service.answer)
    found = [
        (r["question"], r["profile"], r["differences"])
        for r in rows
        if r["differences"]
    ]
    assert found == [("Q2", "second_language", ["declined differently"])]
