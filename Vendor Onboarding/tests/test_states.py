"""Phase 9 checkpoint: every forbidden move is refused, every allowed move works, retries are bounded."""
import itertools

import pytest

from vendor_desk import audit, casestore, config
from vendor_desk.states import ALLOWED, PERSON_ONLY, TERMINAL, IllegalMove, RetryBudget, State, make_move

ALL = list(State)


def test_every_forbidden_move_is_refused():
    forbidden = [(a, b) for a, b in itertools.product(ALL, ALL) if b not in ALLOWED[a]]
    assert len(forbidden) > 30
    for a, b in forbidden:
        with pytest.raises(IllegalMove):
            make_move(a, b, "test", by_person=True)       # even a person cannot make a move that is not allowed


def test_the_moves_that_must_never_happen():
    for a, b in [(State.WAITING_FOR_VENDOR, State.CREATED), (State.CHECKING, State.CREATED),
                 (State.READY_FOR_APPROVAL, State.CREATED), (State.STOPPED, State.CREATED),
                 (State.CHECKING, State.APPROVED), (State.WAITING_FOR_VENDOR, State.APPROVED),
                 (State.STOPPED, State.APPROVED), (State.REJECTED, State.CHECKING), (State.CREATED, State.REJECTED),
                 (State.RECEIVED, State.READY_FOR_APPROVAL)]:
        with pytest.raises(IllegalMove):
            make_move(a, b, "test", by_person=True)


def test_every_allowed_move_works_and_is_recorded():
    for a in ALL:
        for b in ALLOWED[a]:
            m = make_move(a, b, "because", actor="alex", by_person=True)
            assert (m.from_state, m.to_state, m.reason, m.actor) == (a.value, b.value, "because", "alex") and m.at


def test_a_system_step_cannot_make_a_persons_decision():
    for a, b in PERSON_ONLY:
        with pytest.raises(IllegalMove, match="person"):
            make_move(a, b, "auto", by_person=False)
        make_move(a, b, "ok", actor="p", by_person=True)


def test_terminal_states_have_no_exits_and_new_cases_start_received():
    assert all(not ALLOWED[s] for s in TERMINAL)
    assert make_move(None, State.RECEIVED, "new").to_state == "RECEIVED"
    with pytest.raises(IllegalMove):
        make_move(None, State.CHECKING, "skipped RECEIVED")


def test_a_move_needs_a_reason():
    with pytest.raises(IllegalMove):
        make_move(State.RECEIVED, State.CHECKING, "  ")


def test_the_case_record_refuses_an_illegal_move_and_stays_unchanged(runs):
    case = casestore.new_case("VOB-777", "REQ-001")
    casestore.save(case)
    casestore.transition(case, State.RECEIVED, "received")
    casestore.transition(case, State.CHECKING, "go")
    with pytest.raises(IllegalMove):
        casestore.transition(case, State.CREATED, "shortcut", by_person=True)
    assert casestore.load("VOB-777")["status"] == "CHECKING"
    moves = casestore.load("VOB-777")["moves"]
    assert [m["to_state"] for m in moves] == ["RECEIVED", "CHECKING"] and all(m["at"] and m["reason"] for m in moves)
    ok, _ = audit.verify("VOB-777")
    assert ok


def test_retry_budget_is_bounded():
    b = RetryBudget(handoff_limit=2, tool_error_limit=3)
    assert b.record("tool_error") is None and b.record("tool_error") is None
    assert "tool errors" in b.record("tool_error")
    assert b.record("handoff") is None and "handoff failures" in b.record("handoff")


def test_audit_trail_detects_tampering_and_never_holds_private_data(runs):
    audit.append("VOB-778", "documents", "tool_call", "check_bank_country", "Account number: 99310442 sort code 99-10-01")
    audit.append("VOB-778", "system", "state_change", "CHECKING -> STOPPED: test")
    text = audit.audit_path("VOB-778").read_text(encoding="utf-8")
    assert "99310442" not in text and "99-10-01" not in text
    assert audit.verify("VOB-778")[0]
    lines = text.splitlines()
    audit.audit_path("VOB-778").write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")   # delete the first line
    assert not audit.verify("VOB-778")[0]
