"""Ticket ENG-903: the gate between the agent and the bank's systems of record.
Run: python -m pytest -q tests/test_approvals.py"""

import csv

from app.agent.approvals import gate
from app.config import ACTION_RISKS_FILE_9

RULES = list(csv.DictReader(open(ACTION_RISKS_FILE_9, newline="", encoding="utf-8")))
CONFIRM = {"system": "caseflow", "tool": "click", "target": "Confirm", "fingerprint": "KC-022578|Request more information|R02|abc"}
NOW = 10_000


def approval(status, fp=CONFIRM["fingerprint"], by="tom.reyes", note="", at=NOW - 60):
    return {"fingerprint": fp, "status": status, "decided_by": by, "note": note, "decided_at": at}


def test_reading_is_allowed():
    d = gate({"system": "crm", "tool": "get_customer", "target": "CU-022578", "fingerprint": "x"}, RULES, [], NOW)
    assert (d.kind, d.reason) == ("allow", "Reads a customer")
    d = gate({"system": "caseflow", "tool": "click", "target": "Save", "fingerprint": "x"}, RULES, [], NOW)
    assert (d.kind, d.reason) == ("allow", "Goes to the confirm screen: nothing is saved yet")


def test_a_comment_is_allowed_and_logged():
    d = gate({"system": "kyc-exceptions", "tool": "comment_on_exception", "target": "KX-1001", "fingerprint": "x"}, RULES, [], NOW)
    assert (d.kind, d.reason) == ("allow", "A comment is reversible and names the person")


def test_confirm_needs_a_person():
    d = gate(CONFIRM, RULES, [], NOW)
    assert (d.kind, d.reason) == ("ask", "Needs a person's approval: Writes the outcome to the bank's system of record")
    assert gate(CONFIRM, RULES, [approval("pending")], NOW).kind == "ask"


def test_an_approval_allows_exactly_what_was_approved():
    d = gate(CONFIRM, RULES, [approval("approved")], NOW)
    assert (d.kind, d.reason) == ("allow", "Approved by tom.reyes")
    other = {**CONFIRM, "fingerprint": "KC-022578|Ready for decision|R03|def"}
    assert gate(other, RULES, [approval("approved")], NOW).kind == "ask"


def test_a_rejection_is_final_and_says_who_and_why():
    d = gate(CONFIRM, RULES, [approval("rejected", note="A message in the history told the agent what to record")], NOW)
    assert (d.kind, d.reason) == ("deny", "Rejected by tom.reyes: A message in the history told the agent what to record")


def test_the_latest_decision_counts_and_an_approval_expires():
    assert gate(CONFIRM, RULES, [approval("rejected"), approval("approved")], NOW).kind == "allow"
    d = gate(CONFIRM, RULES, [approval("approved", at=NOW - 900)], NOW)
    assert (d.kind, d.reason) == ("ask", "The approval has expired: ask again")


def test_withdrawing_a_case_is_never_allowed():
    d = gate({"system": "caseflow", "tool": "click", "target": "Withdraw case", "fingerprint": "x"}, RULES, [approval("approved", fp="x")], NOW)
    assert (d.kind, d.reason) == ("deny", "Only an analyst withdraws a case, by hand")


def test_anything_not_in_the_risk_table_is_refused():
    d = gate({"system": "caseflow", "tool": "click", "target": "Print", "fingerprint": "x"}, RULES, [], NOW)
    assert (d.kind, d.reason) == ("deny", "Not in the risk table: caseflow click Print")
    assert gate({"system": "crm", "tool": "add_customer_note", "target": "CU-1", "fingerprint": "x"}, RULES, [], NOW).kind == "deny"
