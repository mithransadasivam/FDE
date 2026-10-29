"""Product features, batch 2: settings and branding, users and roles, sign-in security, the checklist and the help page."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import branding
from app.auth import LOCK_MINUTES, MAX_FAILED, check_password_policy
from app.main import app
from app.models import DecisionLog, User
from scripts.create_users import DEMO_PASSWORD


def sign_in(email, password=DEMO_PASSWORD):
    c = TestClient(app, follow_redirects=False)
    c.__enter__()
    r = c.post("/login", data={"email": email, "password": password})
    return c, r


# ---- settings and branding -------------------------------------------------------------------------------------------------------------------
def test_only_the_hiring_manager_sees_settings_and_saving_changes_the_brand_everywhere(platform, db):
    assert platform.rc.get("/settings").status_code == 403
    assert platform.visitor.get("/settings").status_code in (303, 401, 403)
    r = platform.hm.post("/settings", data={"company_name": "Northgate Talent", "tagline": "Fair hiring", "accent": "#0ea5a4",
                                            "support_email": "talent@northgate.example", "welcome": "Join us."})
    assert r.status_code == 303
    for client in (platform.hm, platform.rc, platform.visitor):
        html = client.get("/jobs" if client is platform.visitor else "/").text
        assert "Northgate Talent" in html and "#0ea5a4" in html
    db.expire_all()
    log = db.query(DecisionLog).filter(DecisionLog.action == "company settings changed").one()
    assert log.actor == "hm@example.com" and "company_name" in log.reason


def test_bad_settings_are_refused(platform, db):
    for bad in ({"company_name": "x", "accent": "#0ea5a4"}, {"company_name": "Fine Name", "accent": "blue"},
                {"company_name": "Fine Name", "accent": "#0ea5a4", "support_email": "not-an-email"}):
        platform.hm.post("/settings", data=bad)
    assert "Northgate" not in platform.hm.get("/").text and branding.load(db)["company_name"] == "Hiring Intelligence"


# ---- users and roles ---------------------------------------------------------------------------------------------------------------------------------
def test_the_hiring_manager_adds_a_user_with_a_role_and_the_action_is_logged(platform, db):
    assert platform.rc.get("/users").status_code == 403
    platform.hm.post("/users", data={"name": "Ana Auditor", "email": "ana@example.com", "role": "auditor", "password": ""})
    page = platform.hm.get("/users").text
    assert "ana@example.com" in page and "Temporary password for ana@example.com" in page
    assert "Temporary password" not in platform.hm.get("/users").text  # shown once
    db.expire_all()
    u = db.query(User).filter_by(email="ana@example.com").one()
    assert u.role == "auditor" and u.is_active
    assert db.query(DecisionLog).filter(DecisionLog.action == "user created").one().actor == "hm@example.com"


def test_new_users_need_a_strong_password_and_a_new_email(platform, db):
    platform.hm.post("/users", data={"name": "Weak", "email": "weak@example.com", "role": "recruiter", "password": "short1"})
    platform.hm.post("/users", data={"name": "Dup", "email": "recruiter@example.com", "role": "recruiter", "password": "a-fine-password1"})
    db.expire_all()
    assert db.query(User).filter_by(email="weak@example.com").count() == 0 and db.query(User).count() == 2
    assert check_password_policy("short1", "x@y.z") and check_password_policy("alllettersnodigit") and not check_password_policy("a-fine-password1")


def test_an_auditor_can_read_analytics_the_log_and_the_audit_bundle_and_nothing_else(platform, db):
    platform.hm.post("/users", data={"name": "Ana", "email": "ana@example.com", "role": "auditor", "password": "auditor-pass-9"})
    c, r = sign_in("ana@example.com", "auditor-pass-9")
    assert r.status_code == 303
    for ok in ("/analytics", "/log", "/export/decision-log.csv", "/export/audit.json", "/help", "/account"):
        assert c.get(ok).status_code == 200, ok
    for no in ("/candidates", "/requisitions", "/interviews", "/screening", "/outbox", "/pipeline", "/users", "/settings", "/compare"):
        assert c.get(no).status_code == 403, no
    assert c.post("/pipeline/move", data={"candidate_id": 1, "to": "WITHDRAWN", "reason": "x"}).status_code == 403
    nav = c.get("/analytics").text
    assert "Decision log" in nav and 'href="/candidates"' not in nav and 'href="/requisitions"' not in nav


def test_deactivating_a_user_signs_them_out_and_stops_new_sign_ins(platform, db):
    platform.hm.post("/users", data={"name": "Rae", "email": "rae@example.com", "role": "recruiter", "password": "recruiter-pass-9"})
    c, r = sign_in("rae@example.com", "recruiter-pass-9")
    assert c.get("/candidates").status_code == 200
    rae = db.query(User).filter_by(email="rae@example.com").one()
    platform.hm.post(f"/users/{rae.id}/active", data={"active": "0"})
    assert c.get("/candidates").status_code == 303  # signed out at the next request
    again, r2 = sign_in("rae@example.com", "recruiter-pass-9")
    assert r2.status_code == 403 and "deactivated" in r2.text
    platform.hm.post(f"/users/{rae.id}/active", data={"active": "1"})
    assert sign_in("rae@example.com", "recruiter-pass-9")[1].status_code == 303
    db.expire_all()
    assert {"user deactivated", "user reactivated"} <= {e.action for e in db.query(DecisionLog)}


def test_changing_a_role_and_resetting_a_password(platform, db):
    platform.hm.post("/users", data={"name": "Rae", "email": "rae@example.com", "role": "recruiter", "password": "recruiter-pass-9"})
    rae = db.query(User).filter_by(email="rae@example.com").one()
    platform.hm.post(f"/users/{rae.id}/role", data={"role": "auditor"})
    db.expire_all()
    assert db.get(User, rae.id).role == "auditor"
    platform.hm.post(f"/users/{rae.id}/reset")
    assert "Temporary password for rae@example.com" in platform.hm.get("/users").text
    assert sign_in("rae@example.com", "recruiter-pass-9")[1].status_code == 401  # the old password no longer works
    me = db.query(User).filter_by(email="hm@example.com").one()
    assert platform.hm.post(f"/users/{me.id}/active", data={"active": "0"}).status_code == 400  # not your own access


# ---- sign-in security ---------------------------------------------------------------------------------------------------------------------------------
def test_five_wrong_passwords_lock_the_account_for_fifteen_minutes(platform, db):
    for _ in range(MAX_FAILED):
        assert sign_in("recruiter@example.com", "wrong-password")[1].status_code == 401
    locked, r = sign_in("recruiter@example.com", DEMO_PASSWORD)  # even the right password is refused while locked
    assert r.status_code == 403 and "locked" in r.text
    db.expire_all()
    u = db.query(User).filter_by(email="recruiter@example.com").one()
    assert u.locked_until is not None and db.query(DecisionLog).filter(DecisionLog.action == "sign-in locked").count() == 1
    u.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)  # the lock runs out after LOCK_MINUTES
    db.commit()
    assert LOCK_MINUTES == 15 and sign_in("recruiter@example.com", DEMO_PASSWORD)[1].status_code == 303


def test_a_right_password_resets_the_count(platform, db):
    for _ in range(MAX_FAILED - 1):
        sign_in("hm@example.com", "wrong-password")
    assert sign_in("hm@example.com", DEMO_PASSWORD)[1].status_code == 303
    for _ in range(MAX_FAILED - 1):
        sign_in("hm@example.com", "wrong-password")
    assert sign_in("hm@example.com", DEMO_PASSWORD)[1].status_code == 303  # never reached 5 in a row


def test_a_user_changes_their_own_password(platform, db):
    platform.rc.post("/account/password", data={"current": "wrong", "new": "brand-new-pass-1", "again": "brand-new-pass-1"})
    assert sign_in("recruiter@example.com", "brand-new-pass-1")[1].status_code == 401
    platform.rc.post("/account/password", data={"current": DEMO_PASSWORD, "new": "short", "again": "short"})
    platform.rc.post("/account/password", data={"current": DEMO_PASSWORD, "new": "brand-new-pass-1", "again": "brand-new-pass-1"})
    assert sign_in("recruiter@example.com", "brand-new-pass-1")[1].status_code == 303


def test_security_headers_are_on_every_response(platform):
    for path in ("/login", "/jobs", "/"):
        h = platform.hm.get(path).headers
        assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY" and h["referrer-policy"] == "same-origin"
        assert "camera=()" in h["permissions-policy"] and "microphone=(self)" in h["permissions-policy"]
        assert "default-src 'self'" in h["content-security-policy"] and "frame-ancestors 'none'" in h["content-security-policy"]


# ---- the checklist and help -------------------------------------------------------------------------------------------------------------------------
def test_the_overview_shows_a_getting_started_checklist_that_fills_in(platform, db):
    html = platform.hm.get("/").text
    assert 'data-testid="checklist"' in html and "Getting started" in html
    first = html.count('class="badge good">done')
    platform.apply("C-001_cv.pdf")
    assert platform.hm.get("/").text.count('class="badge good">done') > first


def test_the_help_page_explains_the_flow_roles_and_rules(platform):
    html = platform.rc.get("/help").text
    for needle in ("The flow", "Who can do what", "The twelve rules", "scorers disagree: please review", "Auditor"):
        assert needle in html, needle
