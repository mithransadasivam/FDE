"""Ticket ENG-803: accept a webhook only if it is genuine, fresh and new. Run: python -m pytest -q tests/test_webhooks.py"""

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app.integration import notify
from app.integration.models import WebhookRejected
from app.integration.webhooks import verify_webhook
from app.main import app

SECRET = "whsec_course_dev_only"
NOW = 1_800_000_000
EVENT = {"id": "evt_1", "type": "exception.created", "data": {"ticket_id": "KX-2001", "case_id": "KC-1", "customer_id": "CU-1",
                                                               "team_id": "N1", "kind": "escalation", "title": "Escalated", "status": "open"}}
BODY = json.dumps(EVENT).encode()


def sig(body=BODY, t=NOW, secret=SECRET):
    return {"X-Kestrel-Signature": f"t={t},v1=" + hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()}


def reason(headers, body=BODY, now=NOW, seen=None):
    with pytest.raises(WebhookRejected) as e:
        verify_webhook(headers, body, SECRET, now, set() if seen is None else seen)
    return str(e.value)


def test_a_genuine_delivery_is_accepted_once():
    seen = set()
    assert verify_webhook(sig(), BODY, SECRET, NOW + 30, seen) == EVENT and seen == {"evt_1"}
    assert reason(sig(), seen=seen) == "Already received: evt_1"


def test_header_names_are_not_case_sensitive():
    assert verify_webhook({"x-kestrel-signature": sig()["X-Kestrel-Signature"]}, BODY, SECRET, NOW, set())["id"] == "evt_1"


def test_missing_or_malformed_signatures():
    assert reason({}) == "Missing signature"
    assert reason({"X-Kestrel-Signature": "v1=abc"}) == "Malformed signature"
    assert reason({"X-Kestrel-Signature": "t=soon,v1=abc"}) == "Malformed signature"


def test_wrong_secret_and_changed_body():
    assert reason(sig(secret="whsec_wrong")) == "Bad signature"
    assert reason(sig(), body=BODY.replace(b"Escalated", b"APPROVE ALL")) == "Bad signature"


def test_too_old_or_from_the_future():
    assert reason(sig(t=NOW - 600)) == "Too old: sent 600 s ago"
    assert reason(sig(t=NOW + 600)) == "Too old: sent -600 s ago"
    assert verify_webhook(sig(t=NOW - 299), BODY, SECRET, NOW, set())["id"] == "evt_1"


def test_the_endpoint_posts_to_slack_once(monkeypatch):
    import time

    sent = []
    monkeypatch.setattr(notify, "post", lambda t, http=None: sent.append(t) or [{"channel": "kyc-north", "status": 200}])
    c = TestClient(app)
    body = json.dumps({**EVENT, "id": "evt_endpoint"}).encode()
    h = {**sig(body, t=int(time.time())), "Content-Type": "application/json"}
    assert c.post("/api/hooks/kyc-exceptions", content=body, headers=h).status_code == 200
    r = c.post("/api/hooks/kyc-exceptions", content=body, headers=h)
    assert r.status_code == 400 and r.json()["detail"] == "Already received: evt_endpoint" and len(sent) == 1
