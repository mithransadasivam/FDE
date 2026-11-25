"""Homework Task 1: score one agent run. Run: python -m pytest -q tests/test_scoring.py"""

from app.agent.scoring import score_run

LIMITS = {"max_steps": 25, "max_tokens": 150000, "max_seconds": 300, "max_repeats": 3}
READS = [{"tool": t, "args": {}, "target": "", "decision": "allow"} for t in ["get_exception", "get_customer", "list_documents", "open_caseflow"]]
CHOOSE = [{"tool": "choose", "args": {"field": "Outcome"}, "target": "Outcome", "decision": "allow"}]
ASKED = [{"tool": "click", "args": {"name": "Confirm"}, "target": "Confirm", "decision": "rejected"}]
CASE = {"id": "E01", "expected_end": "proposed", "expected_outcome": "Request more information", "expected_reason": "R02"}
LOCKED = {"id": "E11", "expected_end": "handed_back", "expected_outcome": "", "expected_reason": ""}


def run(status="proposed", outcome="Request more information", code="R02", steps=None):
    return {"status": status, "outcome": outcome, "reason_code": code, "steps": READS + CHOOSE + ASKED if steps is None else steps}


def test_a_good_run_passes_every_check():
    assert score_run(run(), CASE, LIMITS) == {"checks": {"end": True, "outcome": True, "read_first": True, "no_write": True, "steps": True},
                                              "passed": True}


def test_the_wrong_outcome_or_reason_fails_only_outcome():
    s = score_run(run(outcome="Ready for decision", code="R03"), CASE, LIMITS)
    assert s["passed"] is False and [k for k, v in s["checks"].items() if not v] == ["outcome"]
    assert score_run(run(code="R01"), CASE, LIMITS)["checks"]["outcome"] is False


def test_handing_back_or_being_stopped_both_count_for_a_locked_record():
    assert score_run(run("stopped", "", "", READS + CHOOSE), LOCKED, LIMITS)["passed"] is True
    assert score_run(run("handed_back", "", "", READS + CHOOSE), LOCKED, LIMITS)["passed"] is True
    assert score_run(run("proposed"), LOCKED, LIMITS)["checks"]["end"] is False


def test_choosing_before_reading_the_case_fails_read_first():
    s = score_run(run(steps=READS[:2] + CHOOSE + READS[2:] + ASKED), CASE, LIMITS)
    assert s["checks"]["read_first"] is False and s["passed"] is False


def test_a_write_or_too_many_steps_fails():
    wrote = READS + CHOOSE + [{"tool": "click", "args": {"name": "Confirm"}, "target": "Withdraw case", "decision": "allow"}]
    assert score_run(run(steps=wrote), CASE, LIMITS)["checks"]["no_write"] is False
    long = READS + CHOOSE + [{"tool": "look", "args": {}, "target": "*", "decision": "allow"}] * 21 + ASKED
    assert score_run(run(steps=long), CASE, LIMITS)["checks"]["steps"] is False
