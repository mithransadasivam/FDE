"""Day 10 smoke tests: they pass from the start. Run: python -m pytest -q tests/test_workflow_smoke.py"""

import json

from bank import core
from app.config import CHASE_POLICY_FILE_10, CRASH_PLAN_FILE_10, QUEUE_EXPECTED_FILE_10, WRITES_FILE_10
from app.workflow import engine, steps
from tests.bankkit import bank


def test_the_days_files_load():
    pol = json.loads(CHASE_POLICY_FILE_10.read_text())
    assert pol["reminder_after_days"] == 3 and pol["escalate_after_days"] == 7
    assert len(steps.write_rules()) == 8 and WRITES_FILE_10.exists()
    assert {p["point"] for p in engine.crash_points()} >= {"now", "after_send_request", "after_confirm"}
    assert QUEUE_EXPECTED_FILE_10.exists() and len(json.loads(CRASH_PLAN_FILE_10.read_text())["cases"]) == 20


def test_a_case_grant_acts_for_the_person_until_it_is_revoked():
    c = bank()
    c.post("/course/reset")
    cred = {"client_id": "fde-workflow", "client_secret": "workflow-secret-dev"}
    r = c.post("/token", data={"grant_type": "urn:ietf:params:oauth:grant-type:token-exchange", "subject_token": core.issue("tom.reyes", core.MCP_RESOURCE, core.PEOPLE["tom.reyes"]["scopes"], "test"),
                               "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
                               "requested_token_type": "urn:ietf:params:oauth:token-type:refresh_token", "resource": "case:KX-1001", **cred})
    assert r.status_code == 200, r.text
    grant = r.json()["access_token"]
    t = c.post("/token", data={"grant_type": "refresh_token", "refresh_token": grant, "resource": "contact", **cred})
    claims = core.verify(t.json()["access_token"], "contact")
    assert claims["sub"] == "tom.reyes" and claims["act"] == {"sub": "fde-workflow"}
    c.post("/revoke", data={"token": grant, **cred})
    t = c.post("/token", data={"grant_type": "refresh_token", "refresh_token": grant, "resource": "contact", **cred})
    assert t.status_code == 400 and "revoked" in t.json()["error_description"]


def test_the_gateway_sends_without_a_key_and_keeps_the_person():
    c = bank()
    c.post("/course/reset")
    tok = core.issue("tom.reyes", "contact", core.PEOPLE["tom.reyes"]["scopes"], "fde-workflow", act={"sub": "fde-workflow"})
    r = c.post("/contact/messages", json={"ticket_id": "KX-1004", "kind": "request", "text": "Please send a document."},
               headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200 and r.json()["by"] == "tom.reyes" and r.json()["via"] == "fde-workflow"
    other = c.post("/contact/messages", json={"ticket_id": "KX-1010", "kind": "request", "text": "Please send a document."},
                   headers={"Authorization": f"Bearer {tok}"})
    assert other.status_code == 404  # KX-1010 is not in Tom's remit


def test_an_applicant_reply_reaches_the_document_store_and_caseflow():
    c = bank()
    c.post("/course/reset")
    out = c.post("/course/applicant-reply", json={"ticket_id": "KX-1001", "doc_type": "utility_bill"}).json()
    assert out["event"]["type"] == "document.received" and out["document"]["customer_id"] == "CU-022578"
    rows = [h["entry"] for h in next(x for x in __import__("bank.legacy", fromlist=["cases"]).cases() if x["case_ref"] == "KC-022578")["history"]]
    assert any(r.startswith("Applicant replied to our request") for r in rows)


def test_course_days_are_counted_from_the_start():
    assert engine.course_day(1000.0, 1000.0 + 3 * engine.days(1)) == 3.0
