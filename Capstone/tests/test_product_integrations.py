"""Product features, batch 3: the blind read-only REST API and its keys, webhooks, and candidates' data rights."""
import hashlib
import hmac
import json
from pathlib import Path

import pytest

from app import integrations
from app.config import get_settings
from app.models import Candidate, DecisionLog
from app.models_ext import ApiKey, CvText, DataRequest, InterviewSession, ItemScoreRow, Webhook, WebhookDelivery
from app.privacy import identity_strings
from tests.sim.runner import run_interview
from tests.test_interview import invited, shortlisted, token  # noqa: F401


@pytest.fixture(autouse=True)
def fresh_limits():
    integrations.reset_limits()


def make_key(platform, db, name="Reporting tool") -> str:
    platform.hm.post("/integrations/keys", data={"name": name})
    page = platform.hm.get("/integrations").text
    return page.split("<code>")[1].split("</code>")[0]


# ---- keys ------------------------------------------------------------------------------------------------------------------------------------------
def test_a_key_is_shown_once_and_only_its_hash_is_kept(invited, db):
    key = make_key(invited, db)
    assert key.startswith("hi_live_") and "new-key" not in invited.hm.get("/integrations").text  # not shown again
    row = db.query(ApiKey).one()
    assert row.key_hash == hashlib.sha256(key.encode()).hexdigest() and key not in (row.key_hash + row.prefix + row.name) and row.prefix == key[:12]
    assert invited.rc.get("/integrations").status_code == 403  # only the hiring manager
    assert db.query(DecisionLog).filter(DecisionLog.action == "API key created").one().actor == "hm@example.com"


def test_the_api_refuses_a_missing_wrong_or_revoked_key(invited, db):
    assert invited.visitor.get("/api/v1/requisitions").status_code == 401
    assert invited.visitor.get("/api/v1/requisitions", headers={"Authorization": "Bearer nope"}).status_code == 401
    key = make_key(invited, db)
    assert invited.visitor.get("/api/v1/requisitions", headers={"Authorization": f"Bearer {key}"}).status_code == 200
    assert invited.visitor.get("/api/v1/requisitions", headers={"X-API-Key": key}).status_code == 200
    invited.hm.post(f"/integrations/keys/{db.query(ApiKey).one().id}/revoke")
    assert invited.visitor.get("/api/v1/requisitions", headers={"X-API-Key": key}).status_code == 401
    db.expire_all()
    assert db.query(ApiKey).one().last_used_at is not None


def test_the_api_is_read_only_and_blind(invited, db):
    key = make_key(invited, db)
    h = {"Authorization": f"Bearer {key}"}
    run_interview(db, db.get(Candidate, 1), db.get(__import__("app.models", fromlist=["Requisition"]).Requisition, 1), "strong")
    listing = invited.visitor.get("/api/v1/requisitions/1/candidates?stage=AI_INTERVIEW", headers=h).json()
    assert [c["candidate"] for c in listing] == [1] and listing[0]["cv_total_100"] > 0
    one = invited.visitor.get("/api/v1/candidates/1", headers=h).json()
    assert one["cv_scores"] and one["ai_interview"]["overall_100"] > 50 and one["ai_interview"]["levels"]
    everything = json.dumps([one, listing, invited.visitor.get("/api/v1/requisitions", headers=h).json(), invited.visitor.get("/api/v1/events", headers=h).json()])
    for c in db.query(Candidate):
        for secret in identity_strings(c.profile):
            assert secret.lower() not in everything.lower(), secret
    for method in ("post", "put", "delete", "patch"):
        assert getattr(invited.visitor, method)("/api/v1/candidates/1", headers=h).status_code in (404, 405)  # there is nothing to change through the API
    assert invited.visitor.get("/api/v1/candidates/999", headers=h).status_code == 404


def test_events_feed_can_be_polled_and_hides_staff_emails(invited, db):
    key = make_key(invited, db)
    events = invited.visitor.get("/api/v1/events?after=0&limit=500", headers={"X-API-Key": key}).json()
    assert events and all("@" not in e["actor"] for e in events) and {"actor", "action", "subject", "reason"} <= set(events[0])
    later = invited.visitor.get(f"/api/v1/events?after={events[-1]['id']}", headers={"X-API-Key": key}).json()
    assert later == [] or later[0]["id"] > events[-1]["id"]


def test_the_rate_limit_is_sixty_requests_a_minute_per_key(invited, db):
    key = make_key(invited, db)
    codes = [invited.visitor.get("/api/v1/health", headers={"X-API-Key": key}).status_code for _ in range(integrations.RATE_LIMIT + 3)]
    assert codes.count(200) == integrations.RATE_LIMIT and codes[-1] == 429


# ---- webhooks -----------------------------------------------------------------------------------------------------------------------------------------
def add_hook(platform, events=("interview.finished", "shortlist.approved", "decision.recorded", "person.requested")):
    platform.hm.post("/integrations/webhooks", data={"url": "https://example.com/hook", "event": list(events)})


def test_webhooks_are_recorded_but_not_sent_unless_live(invited, db):
    add_hook(invited)
    assert db.query(Webhook).one().events and db.query(Webhook).one().secret
    from app.models import Requisition
    run_interview(db, db.get(Candidate, 1), db.get(Requisition, 1), "strong")
    db.expire_all()
    deliveries = db.query(WebhookDelivery).all()
    assert [d.event for d in deliveries] == ["interview.finished"] and deliveries[0].status == "not_sent"
    assert deliveries[0].payload["candidate"] == 1 and "name" not in json.dumps(deliveries[0].payload).lower()
    assert "WEBHOOKS_LIVE is off" in invited.hm.get("/integrations").text and "test mode" in invited.hm.get("/integrations").text


def test_a_live_webhook_is_signed_and_a_broken_receiver_never_breaks_hiring(invited, db, monkeypatch):
    add_hook(invited)
    monkeypatch.setattr(get_settings(), "webhooks_live", True)
    sent = {}

    class Reply:
        status_code, is_success = 200, True

    import httpx

    def fake_post(url, content, timeout, headers):
        sent.update(url=url, body=content, headers=headers)
        return Reply()

    monkeypatch.setattr(httpx, "post", fake_post)
    invited.hm.post("/integrations/test")
    hook = db.query(Webhook).one()
    hook.events = hook.events + ["test"]
    db.commit()
    invited.hm.post("/integrations/test")
    assert sent["headers"]["X-Signature"] == "sha256=" + hmac.new(hook.secret.encode(), sent["body"], hashlib.sha256).hexdigest() and sent["headers"]["X-Event"] == "test"
    db.expire_all()
    assert db.query(WebhookDelivery).one().status == "sent"

    def broken(*a, **k):
        raise TimeoutError("receiver is down")

    monkeypatch.setattr(httpx, "post", broken)
    assert invited.rc.post("/shortlist/approve", data={"req": 1, "candidate_id": [1], "reason": "x"}).status_code in (303, 404)
    assert integrations.emit(db, "test", {}) == 1
    db.commit()
    assert db.query(WebhookDelivery).order_by(WebhookDelivery.id.desc()).first().status == "failed"


def test_webhook_input_is_checked_and_removing_one_stops_deliveries(invited, db):
    invited.hm.post("/integrations/webhooks", data={"url": "ftp://bad", "event": ["test"]})
    invited.hm.post("/integrations/webhooks", data={"url": "https://example.com/h"})  # no event chosen
    assert db.query(Webhook).count() == 0
    add_hook(invited, events=("person.requested",))
    invited.hm.post(f"/integrations/webhooks/{db.query(Webhook).one().id}/delete")
    from app.agents.interviewer import request_person
    request_person(db, db.get(Candidate, 1))
    db.commit()
    assert db.query(WebhookDelivery).count() == 0


# ---- candidates' data rights -------------------------------------------------------------------------------------------------------------------------
def test_a_candidate_downloads_a_copy_of_their_data(invited, db):
    from app.models import Requisition
    run_interview(db, db.get(Candidate, 1), db.get(Requisition, 1), "strong")
    t = token(db)
    r = invited.visitor.get(f"/me/{t}/data.json")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = r.json()
    assert data["application"]["candidate_number"] == 1 and data["details_read_from_your_cv"]["name"] and data["cv_scores"] and data["stage_history"]
    assert data["ai_interview"]["questions_and_answers"] and data["your_rights"]
    assert invited.visitor.get("/me/not-a-token/data.json").status_code == 404
    db.expire_all()
    assert db.query(DecisionLog).filter(DecisionLog.action == "data copy downloaded").count() == 1


def test_asking_for_deletion_erases_nothing_until_a_person_approves(invited, db):
    t = token(db)
    invited.visitor.post(f"/me/{t}/delete-request")
    invited.visitor.post(f"/me/{t}/delete-request")  # asking twice makes one request
    db.expire_all()
    assert db.query(DataRequest).count() == 1 and db.get(Candidate, 1).profile and db.get(Candidate, 1).erased_at is None
    assert "waiting for a recruiter" in invited.visitor.get(f"/me/{t}").text
    assert "Candidate" and invited.hm.get("/data-requests").status_code == 403  # a recruiter decides
    assert "#1" in invited.rc.get("/data-requests").text


def test_a_recruiter_approves_and_personal_data_is_erased_but_the_trail_stays(invited, db):
    from app.models import Requisition
    run_interview(db, db.get(Candidate, 1), db.get(Requisition, 1), "strong")
    db.expire_all()
    cand = db.get(Candidate, 1)
    cv_file, folder = Path(cand.cv_path), get_settings().storage_dir / "interviews" / "1"
    assert cv_file.exists() and folder.exists()
    t = token(db)
    invited.visitor.post(f"/me/{t}/delete-request")
    req = db.query(DataRequest).one()
    invited.rc.post(f"/data-requests/{req.id}/decide", data={"decision": "approve", "reason": "  "})  # no reason: refused
    db.expire_all()
    assert db.query(DataRequest).one().status == "REQUESTED"
    invited.rc.post(f"/data-requests/{req.id}/decide", data={"decision": "approve", "reason": "the candidate withdrew consent"})
    db.expire_all()
    cand = db.get(Candidate, 1)
    assert cand.erased_at and cand.profile is None and cand.cv_path == "" and cand.cv_name == "[erased]" and cand.stage == "WITHDRAWN"
    assert not cv_file.exists() and not folder.exists()
    assert db.query(CvText).filter_by(candidate_id=1).count() == 0 and db.query(ItemScoreRow).filter_by(candidate_id=1).count() == 0
    assert db.query(InterviewSession).filter_by(candidate_id=1).count() == 0
    log = [e for e in db.query(DecisionLog) if e.subject == "candidate:1"]
    assert all(e.evidence is None or e.action == "personal data erased" for e in log)  # no quotes remain in the log
    assert {"asked for their data to be deleted", "personal data erased"} <= {e.action for e in log}
    assert db.query(DecisionLog).filter(DecisionLog.action == "move AI_INTERVIEW -> WITHDRAWN").one().actor == "recruiter@example.com"
    page = invited.visitor.get(f"/me/{t}").text
    assert "personal data was erased" in page
    assert invited.visitor.get(f"/me/{t}/data.json").status_code == 410
    assert db.get(Candidate, 2).profile  # nobody else is touched


def test_a_refusal_needs_a_reason_and_the_candidate_sees_it(invited, db):
    t = token(db)
    invited.visitor.post(f"/me/{t}/delete-request")
    req = db.query(DataRequest).one()
    invited.rc.post(f"/data-requests/{req.id}/decide", data={"decision": "refuse", "reason": ""})
    db.expire_all()
    assert db.query(DataRequest).one().status == "REQUESTED"
    invited.rc.post(f"/data-requests/{req.id}/decide", data={"decision": "refuse", "reason": "a legal hold applies while the complaint is open"})
    db.expire_all()
    assert db.get(Candidate, 1).profile and "a legal hold applies" in invited.visitor.get(f"/me/{t}").text
    assert invited.rc.post(f"/data-requests/{req.id}/decide", data={"decision": "approve", "reason": "x"}).status_code == 303
    db.expire_all()
    assert db.query(DataRequest).one().status == "REFUSED"  # already decided: not changed


def test_the_api_and_webhooks_are_hidden_unless_switched_on(db):
    """With ENABLE_INTEGRATIONS off (the default) the API, keys and webhooks are not mounted at all, but candidates' data rights stay on."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.web import integrations as module

    off = FastAPI()
    off.include_router(module.router)  # what main.py always mounts
    on = FastAPI()
    on.include_router(module.router)
    on.include_router(module.api_router)
    with TestClient(off) as c:
        assert c.get("/api/v1/health").status_code == 404 and c.get("/integrations").status_code == 404
        assert c.post("/integrations/keys", data={"name": "x"}).status_code == 404
        assert c.get("/me/not-a-token/data.json").status_code == 404  # this route exists (the token is what is unknown)
    with TestClient(on) as c:
        assert c.get("/api/v1/health").status_code == 401  # mounted: it asks for a key
    from app.config import Settings

    assert Settings.model_fields["enable_integrations"].default is False  # off unless ENABLE_INTEGRATIONS=1 is set (the tests set it)
