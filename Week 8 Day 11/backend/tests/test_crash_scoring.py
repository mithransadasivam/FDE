"""Homework Task 1: score one case of the crash test. Run: python -m pytest -q tests/test_crash_scoring.py"""

from app.workflow.scoring import score_case

CASE = {"id": "C04", "ticket_id": "KX-1008", "expected_end": "escalated",
        "expected": {"requests": 1, "reminders": 1, "escalations": 1, "caseflow_outcomes": 1, "outcome_comments": 1}}


def result(**changes):
    counts = {"requests": 1, "reminders": 1, "escalations": 1, "caseflow_outcomes": 1, "outcome_comments": 1, **changes.pop("counts", {})}
    return {"key": "case-KX-1008-1", "ticket_id": "KX-1008", "end": "escalated", "counts": counts, "agent_runs": {"1": 1},
            "crashes": ["after_escalate"], **changes}


def test_a_clean_case_passes_every_check():
    s = score_case(result(), CASE)
    assert s["checks"] == {"end": True, "messages": True, "caseflow": True, "escalation": True, "agent_once": True}
    assert s["passed"] is True


def test_the_wrong_end_fails_only_end():
    s = score_case(result(end="completed"), CASE)
    assert s["checks"]["end"] is False and s["passed"] is False
    assert all(v for k, v in s["checks"].items() if k != "end")


def test_a_message_sent_twice_fails_messages():
    assert score_case(result(counts={"requests": 2}), CASE)["checks"]["messages"] is False
    assert score_case(result(counts={"reminders": 0}), CASE)["checks"]["messages"] is False


def test_an_outcome_or_comment_written_twice_fails_caseflow():
    assert score_case(result(counts={"caseflow_outcomes": 2}), CASE)["checks"]["caseflow"] is False
    assert score_case(result(counts={"outcome_comments": 2}), CASE)["checks"]["caseflow"] is False
    assert score_case(result(counts={"escalations": 2}), CASE)["checks"]["escalation"] is False


def test_an_agent_that_ran_twice_in_a_round_fails_agent_once():
    assert score_case(result(agent_runs={"1": 2}), CASE)["checks"]["agent_once"] is False
    assert score_case(result(agent_runs={"1": 1, "2": 1}), CASE)["checks"]["agent_once"] is True
    assert score_case(result(agent_runs={}), CASE)["checks"]["agent_once"] is True
