"""Ticket ENG-1003: every write happens once, even when the worker crashes halfway through a step.
Run: python -m pytest -q tests/test_writes.py"""

from bank import core
from app.workflow.writes import already_recorded, idempotency_key, outcome_marker
from tests.bankkit import bank


def test_the_same_step_gives_the_same_key():
    assert idempotency_key("case-KX-1004-1", 6) == idempotency_key("case-KX-1004-1", 6), \
        "A step that runs again after a crash must send the same key: never a random value or the time"


def test_the_key_names_the_workflow_and_the_step():
    assert idempotency_key("case-KX-1004-1", 6) == "case-KX-1004-1:6"


def test_every_other_write_gets_its_own_key():
    keys = {idempotency_key("case-KX-1004-1", 6), idempotency_key("case-KX-1004-1", 9), idempotency_key("case-KX-1001-1", 6),
            idempotency_key("case-KX-1004-2", 6)}
    assert len(keys) == 4


def test_the_gateway_sends_once_for_one_key():
    c = bank()
    c.post("/course/reset")
    tok = core.issue("tom.reyes", "contact", core.PEOPLE["tom.reyes"]["scopes"], "fde-workflow", act={"sub": "fde-workflow"})
    body = {"ticket_id": "KX-1004", "kind": "request", "text": "We need one more document to finish checking your application KC-023327."}
    for _ in range(2):  # the step, then the same step again after a crash
        r = c.post("/contact/messages", json=body, headers={"Authorization": f"Bearer {tok}",
                                                             "Idempotency-Key": idempotency_key("case-KX-1004-1", 6)})
        assert r.status_code == 200
    sent = c.get("/course/contact-log", params={"ticket_id": "KX-1004"}).json()["messages"]
    assert len(sent) == 1, f"The applicant got {len(sent)} requests"


def test_the_marker_is_found_in_the_case_history():
    m = outcome_marker("case-KX-1001-1", 1)
    history = ["26/10/2026 | SYSTEM | Application received through the web form.",
               f"17/11/2026 | tom.reyes via fde-mcp, for fde-workflow | Outcome: Request more information (R02). Proof of address needed. {m} Reference OUT-40017."]
    assert already_recorded(history, m)


def test_a_near_miss_is_not_the_marker():
    assert not already_recorded(["… [case-KX-1001-1 r12] Reference OUT-40017."], outcome_marker("case-KX-1001-1", 1))
    assert not already_recorded(["… [case-KX-1001-11 r1] Reference OUT-40017."], outcome_marker("case-KX-1001-1", 1))


def test_an_empty_history_has_no_marker():
    assert not already_recorded([], outcome_marker("case-KX-1001-1", 1))


def test_a_different_round_is_not_recorded_yet():
    history = [f"Outcome: Request more information (R02). {outcome_marker('case-KX-1001-1', 1)} Reference OUT-40017."]
    assert already_recorded(history, outcome_marker("case-KX-1001-1", 1))
    assert not already_recorded(history, outcome_marker("case-KX-1001-1", 2)), "Round 2 records its own outcome"
