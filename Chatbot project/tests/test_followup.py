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
    monkeypatch.setattr(retrieval, "rewrite_queries", lambda q, prev: [f"rewritten({q} | {prev})"])
    found = retrieval.retrieve_detailed("And for P3?", 4, mode="smart", previous_question="What is the P1 response target?")
    assert seen["query"] == "rewritten(And for P3? | What is the P1 response target?)" and found["searched_for"] == seen["query"]


def test_smart_does_not_rewrite_a_standalone_question(monkeypatch):
    seen = fake_search(monkeypatch)
    monkeypatch.setattr(retrieval, "rewrite_queries", lambda q, prev: pytest.fail("must not call the model"))
    found = retrieval.retrieve_detailed("How long can a VPN session stay connected?", 4, mode="smart", previous_question="Something else?")
    assert seen["query"] == found["searched_for"] == "How long can a VPN session stay connected?"


def test_smart_does_not_rewrite_when_there_is_no_previous_question(monkeypatch):
    seen = fake_search(monkeypatch)
    monkeypatch.setattr(retrieval, "rewrite_queries", lambda q, prev: pytest.fail("no earlier question to use"))
    retrieval.retrieve_detailed("And for P3?", 4, mode="smart", previous_question="")
    assert seen["query"] == "And for P3?"


def chunk(source, page, number, score):
    return {"text": f"{source} {number}", "source": source, "page": page, "chunk": number, "score": score}


def test_a_follow_up_keeps_the_first_results_and_adds_extras_from_the_second_query(monkeypatch):
    """CTX-03: the 12-hour limit and 'applies to contractors' sit in different chunks, and only the policy-style query finds the second."""
    results = {"VPN session length for contractors": [chunk("vpn.pdf", 1, 3, 0.70), chunk("kb.pdf", 1, 3, 0.69), chunk("kb.pdf", 1, 2, 0.67), chunk("x.md", 1, 1, 0.60)],
               "VPN policy applies to contractors": [chunk("kb.pdf", 1, 3, 0.72), chunk("vpn.pdf", 1, 3, 0.70), chunk("vpn.pdf", 2, 5, 0.69), chunk("vpn.pdf", 1, 1, 0.68),
                                                     chunk("y.md", 1, 1, 0.5), chunk("z.md", 1, 1, 0.4), chunk("w.md", 1, 1, 0.3), chunk("v.md", 1, 1, 0.2)]}
    monkeypatch.setattr(retrieval, "search", lambda query, k: results[query][:k])
    monkeypatch.setattr(retrieval, "rewrite_queries", lambda q, prev: list(results))
    found = retrieval.retrieve_detailed("Is that the same for contractors?", 4, mode="smart", previous_question="How long can a VPN session stay connected?")
    keys = [(c["source"], c["page"], c["chunk"]) for c in found["chunks"]]
    assert keys[:4] == [("vpn.pdf", 1, 3), ("kb.pdf", 1, 3), ("kb.pdf", 1, 2), ("x.md", 1, 1)]  # the first query's results, untouched and in order
    assert keys[4:] == [("vpn.pdf", 2, 5), ("vpn.pdf", 1, 1)]                                    # then up to 2 new ones from the second query
    assert found["searched_for"] == "VPN session length for contractors | VPN policy applies to contractors"


def test_with_one_query_the_results_are_exactly_the_old_behaviour(monkeypatch):
    one = [chunk("a", 1, n, 1 - n / 10) for n in range(1, 7)]
    monkeypatch.setattr(retrieval, "search", lambda query, k: one[:k])
    monkeypatch.setattr(retrieval, "rewrite_queries", lambda q, prev: ["only one"])
    found = retrieval.retrieve_detailed("And for P3?", 4, mode="smart", previous_question="What is the P1 response target?")
    assert found["chunks"] == one[:4] and found["searched_for"] == "only one"


def test_extras_never_repeat_a_chunk_and_never_exceed_the_limit():
    primary = [chunk("a", 1, 1, 0.9), chunk("b", 1, 1, 0.8)]
    secondary = [chunk("a", 1, 1, 0.9), chunk("c", 1, 1, 0.7), chunk("d", 1, 1, 0.6), chunk("e", 1, 1, 0.5)]
    assert [c["source"] for c in retrieval.add_extras(primary, secondary, 2)] == ["a", "b", "c", "d"]
    assert retrieval.add_extras(primary, secondary, 0) == primary and retrieval.add_extras(primary, [], 2) == primary


def test_a_question_in_another_language_is_searched_with_one_english_query(monkeypatch):
    seen = fake_search(monkeypatch)
    monkeypatch.setattr(retrieval, "to_english_query", lambda q, prev: "daily server backups retention")
    monkeypatch.setattr(retrieval, "rewrite_queries", lambda q, prev: pytest.fail("not for a question in another language"))
    found = retrieval.retrieve_detailed("¿Cuánto tiempo guardan las copias de seguridad diarias de los servidores?", 4, mode="smart")
    assert seen["query"] == found["searched_for"] == "daily server backups retention"


def test_an_english_question_is_never_translated(monkeypatch):
    seen = fake_search(monkeypatch)
    monkeypatch.setattr(retrieval, "to_english_query", lambda q, prev: pytest.fail("English needs no translation"))
    retrieval.retrieve_detailed("How long do you keep daily server backups?", 4, mode="smart")
    assert seen["query"] == "How long do you keep daily server backups?"
