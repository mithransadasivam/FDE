"""Follow-up detection and the "smart" retrieval mode, with fakes (no models, no search)."""
import pytest

from app import retrieval
from app.eval_suite import load_suite
from app.followup import looks_like_follow_up


@pytest.mark.parametrize("question", [
    "And for P3?", "What about on a Mac?", "Is that the same for contractors?", "What if it still fails after that?",
    "and how much notice do I get before it is replaced?", "How about the other one?", "Why?", "Also on Wi-Fi?", "Same for visitors?",
])
def test_follow_ups_are_recognised(question):
    assert looks_like_follow_up(question)


@pytest.mark.parametrize("question", [
    "How long can a VPN session stay connected?", "What does error VPN-806 mean?", "How do I set up MFA on a new phone?",
    "Does Northwind support Linux laptops?", "What should I do if my laptop battery is swelling?", "", "   ",
    "I have a VPN question. It keeps disconnecting every few hours at home, and I am on Windows 11 with the latest client.",
])
def test_standalone_questions_are_not_follow_ups(question):
    assert not looks_like_follow_up(question)


def test_every_follow_up_in_the_suite_is_recognised_and_standalone_cases_mostly_are_not():
    cases = [c for c in load_suite() if c["dimension"] in ("context", "ragas") and c["turns"] and c["expected_behaviour"] == "answer"]
    missed = [c["id"] for c in cases if not looks_like_follow_up(c["input"]) and c["id"] not in ("CTX-06", "CTX-08")]  # those two are topic changes
    assert missed == []


def fake_search(monkeypatch):
    seen = {}

    def search(query, k):
        seen["query"] = query
        return [{"text": "t", "source": "a.md", "page": 1, "score": 0.9}]

    monkeypatch.setattr(retrieval, "search", search)
    return seen


def test_smart_rewrites_a_follow_up_using_the_previous_question(monkeypatch):
    seen = fake_search(monkeypatch)
    monkeypatch.setattr(retrieval, "rewrite_query", lambda q, prev: f"rewritten({q} | {prev})")
    found = retrieval.retrieve_detailed("And for P3?", 4, mode="smart", previous_question="What is the P1 response target?")
    assert seen["query"] == "rewritten(And for P3? | What is the P1 response target?)" and found["searched_for"] == seen["query"]


def test_smart_does_not_rewrite_a_standalone_question(monkeypatch):
    seen = fake_search(monkeypatch)
    monkeypatch.setattr(retrieval, "rewrite_query", lambda q, prev: pytest.fail("must not call the model"))
    found = retrieval.retrieve_detailed("How long can a VPN session stay connected?", 4, mode="smart", previous_question="Something else?")
    assert seen["query"] == found["searched_for"] == "How long can a VPN session stay connected?"


def test_smart_does_not_rewrite_when_there_is_no_previous_question(monkeypatch):
    seen = fake_search(monkeypatch)
    monkeypatch.setattr(retrieval, "rewrite_query", lambda q, prev: pytest.fail("no earlier question to use"))
    retrieval.retrieve_detailed("And for P3?", 4, mode="smart", previous_question="")
    assert seen["query"] == "And for P3?"
