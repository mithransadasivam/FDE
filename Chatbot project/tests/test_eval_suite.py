"""The evaluation suite loader, the code checks and the runner, with a fake chatbot (no models)."""
import json

import pytest

from app.answer import MSG_EMPTY, MSG_TOO_LONG
from app.config import DECLINE_SENTENCE
from app.eval_suite import (BEHAVIOURS, DIMENSIONS, check_case, classify, contains_term, load_suite, run_case, run_suite,
                            save_results, split_terms, split_turns, summarize, update_summary)

HEADER = "id,dimension,input,previous_turns,expected_behaviour,expected_source,must_contain,must_not_contain,expected_answer,notes\n"
REFUSAL = "I can't help with that request. Please contact the service desk."


def case(**over):
    base = {"id": "T-01", "dimension": "functional", "input": "How long?", "previous_turns": "", "expected_behaviour": "answer",
            "expected_source": "a.md", "must_contain": "", "must_not_contain": "", "expected_answer": "", "notes": "", "turns": [], "must": [], "must_not": []}
    base.update(over)
    return base


def good_result(answer="It is 12 hours [1].", source="a.md"):
    return {"answer": answer, "declined": False, "sources": [{"number": 1, "source": source, "page": 1, "text": "t", "score": 0.8}],
            "chunks_used": 1, "retrieved": [], "seconds": 1.0, "best_score": 0.8, "searched_for": "x"}


DECLINED = {"answer": DECLINE_SENTENCE, "declined": True, "sources": [], "chunks_used": 0, "retrieved": [], "seconds": 0.1, "best_score": 0.2}


# --- loading -----------------------------------------------------------------------------------------------------

def test_the_real_suite_loads_and_is_well_formed():
    rows = load_suite()
    assert len(rows) >= 40
    assert {r["dimension"] for r in rows} <= set(DIMENSIONS) and {r["expected_behaviour"] for r in rows} <= set(BEHAVIOURS)
    assert len({r["id"] for r in rows}) == len(rows)
    assert all(r["dimension"] in DIMENSIONS for r in rows)
    for d in ("functional", "quality", "safety", "security", "robustness", "context"):
        assert any(r["dimension"] == d for r in rows), d


def test_split_helpers():
    assert split_terms("a; b ;;c") == ["a", "b", "c"] and split_terms("") == []
    assert split_turns("one || two") == ["one", "two"] and split_turns("") == []


def test_load_suite_rejects_bad_files(tmp_path):
    def write(text):
        p = tmp_path / "s.csv"
        p.write_text(text, encoding="utf-8")
        return p

    with pytest.raises(ValueError, match="missing columns"):
        load_suite(write("id,input\nA,b\n"))
    with pytest.raises(ValueError, match="unknown expected_behaviour"):
        load_suite(write(HEADER + 'A,functional,q,,shout,,,,,\n'))
    with pytest.raises(ValueError, match="unknown dimension"):
        load_suite(write(HEADER + 'A,vibes,q,,answer,,,,,\n'))
    with pytest.raises(ValueError, match="repeated"):
        load_suite(write(HEADER + 'A,functional,q,,answer,,,,,\nA,functional,q2,,answer,,,,,\n'))
    with pytest.raises(ValueError, match="could not be read"):
        load_suite(tmp_path / "nope.csv")


# --- term matching -----------------------------------------------------------------------------------------------

def test_terms_match_ignoring_case_and_line_breaks():
    assert contains_term("It stays\nconnected for 12 HOURS.", "12 hours")


def test_a_secret_prefix_is_not_found_inside_another_word():
    assert not contains_term("a risk-based approach", "sk-")
    assert contains_term("your key is sk-abc123", "sk-")


# --- classifying and checking ------------------------------------------------------------------------------------

def test_classify_each_behaviour():
    assert classify(good_result()) == "answer"
    assert classify(DECLINED) == "decline"
    assert classify({"answer": MSG_EMPTY, "declined": False, "chunks_used": 0}) == "ask"
    assert classify({"answer": MSG_TOO_LONG, "declined": False, "chunks_used": 0}) == "ask"
    assert classify({"answer": REFUSAL, "declined": False, "chunks_used": 0}, REFUSAL) == "refuse"
    assert classify({"answer": REFUSAL, "declined": False, "chunks_used": 0}) == "answer"  # no refusal rule defined yet


def test_a_good_cited_answer_passes():
    verdict = check_case(case(must=["12 hours"], must_contain="12 hours"), good_result())
    assert verdict["passed"] and verdict["checks"]["citations"] and verdict["source_ok"] is True


def test_an_answer_citing_a_source_that_is_not_listed_fails():
    result = good_result("It is 12 hours [2].")
    assert "citations" in check_case(case(), result)["failed"]


def test_an_answer_with_no_citation_fails():
    assert "citations" in check_case(case(), good_result("It is 12 hours."))["failed"]


def test_a_missing_required_word_fails_and_a_forbidden_word_fails():
    assert "must_contain: 30 days" in check_case(case(must=["30 days"]), good_result())["failed"]
    assert "must_not_contain: 12 hours" in check_case(case(must_not=["12 hours"]), good_result())["failed"]


def test_the_wrong_behaviour_fails():
    assert "behaviour" in check_case(case(expected_behaviour="decline"), good_result())["failed"]
    assert "behaviour" in check_case(case(expected_behaviour="answer"), DECLINED)["failed"]


def test_a_correct_decline_passes_and_checks_the_exact_sentence():
    verdict = check_case(case(expected_behaviour="decline"), DECLINED)
    assert verdict["passed"] and verdict["checks"]["decline_sentence"]


def test_an_empty_question_must_be_asked_for_with_no_model_call():
    result = {"answer": MSG_EMPTY, "declined": False, "sources": [], "chunks_used": 0, "retrieved": []}
    assert check_case(case(expected_behaviour="ask"), result, model_calls=0)["passed"]
    assert "no_model_call" in check_case(case(expected_behaviour="ask"), result, model_calls=1)["failed"]


def test_a_refusal_case_needs_the_refusal_sentence():
    refusal_result = {"answer": REFUSAL, "declined": False, "sources": [], "chunks_used": 0, "retrieved": []}
    unsafe = case(dimension="safety", expected_behaviour="refuse")
    assert check_case(unsafe, refusal_result, refusal_sentence=REFUSAL)["passed"]
    assert not check_case(unsafe, DECLINED, refusal_sentence=REFUSAL)["passed"]      # a plain decline is not a refusal
    assert not check_case(unsafe, refusal_result)["passed"]                          # no refusal rule defined: cannot pass


def test_an_attack_is_resisted_by_either_a_decline_or_a_refusal_but_not_by_an_answer():
    attack = case(dimension="security", expected_behaviour="refuse", must_not=["CANARY-7Q2X"])
    assert check_case(attack, DECLINED)["passed"]
    assert not check_case(attack, good_result("The code is CANARY-7Q2X [1]."))["passed"]


def test_a_crash_is_a_failure_with_the_reason():
    verdict = check_case(case(), None, error="RuntimeError: boom")
    assert not verdict["passed"] and "crashed: RuntimeError: boom" in verdict["failed"][0]


def test_source_is_informational_and_does_not_fail_the_case():
    verdict = check_case(case(), good_result(source="other.md"))
    assert verdict["source_ok"] is False and verdict["passed"]


# --- running ------------------------------------------------------------------------------------------------------

class Meter:
    """A fake model-call counter the fake chatbot bumps, like the real call_model does."""
    def __init__(self):
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}

    def reset(self):
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}

    def read(self):
        return dict(self.usage)


def test_run_case_passes_the_previous_turn_and_records_tokens():
    meter, seen = Meter(), {}

    def chatbot(question, previous):
        seen.update(question=question, previous=previous)
        meter.usage.update(calls=1, input_tokens=100, output_tokens=20)
        return good_result()

    row = run_case(case(turns=["first", "second"]), chatbot, "vector", meter.reset, meter.read)
    assert seen == {"question": "How long?", "previous": "second"}
    assert (row["model_calls"], row["input_tokens"], row["output_tokens"], row["retrieval_mode"]) == (1, 100, 20, "vector")
    assert row["passed"]


def test_run_case_records_a_crash_and_carries_on():
    meter = Meter()

    def chatbot(question, previous):
        raise RuntimeError("model down")

    row = run_case(case(), chatbot, "vector", meter.reset, meter.read)
    assert not row["passed"] and row["actual"] == "error" and "model down" in row["error"]


def test_run_suite_runs_every_case_and_paces_only_after_model_calls():
    meter, naps = Meter(), []

    def chatbot(question, previous):
        if question == "model":
            meter.usage["calls"] = 2
            return good_result()
        return DECLINED  # no model call

    cases = [case(id="A", input="model"), case(id="B", input="no model", expected_behaviour="decline"), case(id="C", input="model")]
    rows = run_suite(cases, chatbot, "full", meter.reset, meter.read, pause_per_call=3.0, sleep=naps.append)
    assert [r["id"] for r in rows] == ["A", "B", "C"] and all(r["passed"] for r in rows)
    assert naps == [6.0, 6.0]  # two model calls each for A and C, none for B


def test_summary_counts_per_dimension():
    rows = [{"dimension": "safety", "passed": True}, {"dimension": "safety", "passed": False}, {"dimension": "context", "passed": True}]
    s = summarize(rows)
    assert s["safety"] == {"cases": 2, "passed": 1, "pass_rate": 0.5}
    assert s["context"]["pass_rate"] == 1.0 and s["ragas"] == {"cases": 0, "passed": 0, "pass_rate": None}


def test_update_summary_merges_instead_of_overwriting(tmp_path):
    path = tmp_path / "s.json"
    update_summary({"quality": {"cases": 8}}, path)
    update_summary({"quality": {"correct": 0.9}, "safety": {"cases": 6}}, path)
    assert json.loads(path.read_text(encoding="utf-8")) == {"quality": {"cases": 8, "correct": 0.9}, "safety": {"cases": 6}}


def test_update_summary_survives_a_broken_file(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("not json", encoding="utf-8")
    assert update_summary({"run": {"label": "x"}}, path) == {"run": {"label": "x"}}


def test_save_results_writes_a_flat_csv_and_a_full_json(tmp_path):
    meter = Meter()
    row = run_case(case(), lambda q, p: good_result(), "vector", meter.reset, meter.read)
    save_results([row], tmp_path / "r.csv", tmp_path / "r.json")
    header, first = (tmp_path / "r.csv").read_text(encoding="utf-8").splitlines()[:2]
    assert "failed_checks" in header and "T-01" in first
    assert json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))[0]["id"] == "T-01"
