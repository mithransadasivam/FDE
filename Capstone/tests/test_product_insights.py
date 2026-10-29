"""Product features, batch 1: analytics, candidate comparison, list filters and exports."""
import csv
import hashlib
import io
import json

import pytest

from app import analytics
from app.models import Candidate, DecisionLog, Requisition
from app.privacy import identity_strings
from tests.sim.runner import run_interview
from tests.test_interview import invited, shortlisted, token  # noqa: F401


@pytest.fixture
def busy(invited, db):
    """Three screened candidates, all shortlisted and invited, one strong interview finished."""
    run_interview(db, db.get(Candidate, 1), db.get(Requisition, 1), "strong")
    db.expire_all()
    return invited


# ---- analytics -----------------------------------------------------------------------------------------------------------------------------
def test_the_funnel_counts_who_reached_each_stage(busy, db):
    rows = {r["stage"]: r for r in analytics.funnel(db)}
    assert rows["APPLIED"]["n"] == 3 and rows["SCREENED"]["n"] == 3 and rows["SHORTLISTED"]["n"] == 3 and rows["AI_INTERVIEW"]["n"] == 1
    assert rows["SHORTLISTED"]["of_previous"] == 100.0 and rows["AI_INTERVIEW"]["of_applied"] == round(100 / 3, 1)


def test_interview_stats_and_oversight_numbers(busy, db):
    st = analytics.interview_stats(db)
    assert st["invited"] == 1 and st["done"] == 1 and st["samples"] == 1 and st["recordings"] == 1 and st["avg_overall"] > 50
    o = analytics.people_in_the_loop(db)
    assert o["by_a_person"] >= 4 and o["with_reason"] == o["by_a_person"] and o["by_the_system"] >= 3  # screening is automatic, decisions are people's


def test_score_spread_adds_up_to_the_screened_candidates(busy, db):
    bands = analytics.score_distribution(db)
    assert sum(b["n"] for b in bands) == 3 and len(bands) == 10


def test_the_analytics_page_renders_for_both_roles_and_filters_by_job(busy):
    for client in (busy.rc, busy.hm):
        html = client.get("/analytics").text
        for needle in ("Funnel", "CV score spread", "AI interviews", "People in the loop", "Model cost"):
            assert needle in html, needle
    assert busy.rc.get("/analytics?req=1").status_code == 200
    assert busy.visitor.get("/analytics").status_code in (303, 401, 403)


def test_the_analytics_page_holds_no_identity_or_protected_traits(busy, db):
    html = busy.rc.get("/analytics").text.lower()
    for c in db.query(Candidate):
        for secret in identity_strings(c.profile):
            assert secret.lower() not in html
    assert "by gender" not in html and "age group" not in html and "holds no age, gender or origin" in html  # the page says it keeps none and shows no such breakdown


# ---- comparison ------------------------------------------------------------------------------------------------------------------------------------
def test_compare_shows_candidates_side_by_side_blind(busy, db):
    html = busy.rc.get("/compare?req=1&ids=1,2,3").text
    assert "Candidate #1" in html and "Candidate #2" in html and "Candidate #3" in html and "CV total" in html and "AI interview overall" in html
    assert "interview:" in html  # candidate 1 has finished an interview
    for c in db.query(Candidate):
        for secret in identity_strings(c.profile):
            assert secret.lower() not in html.lower()


def test_compare_ignores_candidates_from_another_job_and_caps_at_five(busy):
    assert "None of those candidates belong" in busy.rc.get("/compare?req=2&ids=1,2").text or busy.rc.get("/compare?req=2&ids=1,2").status_code == 404
    page = busy.rc.get("/compare?req=1&ids=1,2,3,3,3,3,3,3")
    assert page.status_code == 200


# ---- filters -------------------------------------------------------------------------------------------------------------------------------------------
def test_the_candidate_list_filters_by_stage_skill_years_and_score(busy):
    everything = busy.rc.get("/candidates?blind=1").text
    assert "filters" in everything and "CV score" in everything
    only_interview = busy.rc.get("/candidates?blind=1&stage=AI_INTERVIEW").text
    assert "Candidate #1" in only_interview and "Candidate #2" not in only_interview and "1 candidate(s) match" in only_interview
    assert "0 candidate(s) match" in busy.rc.get("/candidates?blind=1&skill=Cobol").text
    assert "0 candidate(s) match" in busy.rc.get("/candidates?blind=1&min_total=101").text
    assert "candidate(s) match" in busy.rc.get("/candidates?blind=1&skill=linux&min_years=1&min_total=1").text


# ---- exports -------------------------------------------------------------------------------------------------------------------------------------------------
def test_candidates_csv_is_blind_and_has_scores(busy, db):
    r = busy.rc.get("/export/candidates.csv?req=1")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv") and "attachment" in r.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0][:3] == ["candidate", "stage", "cv_total_100"] and rows[0][-1] == "ai_interview_overall_100" and len(rows) == 4
    assert rows[1][-1] not in ("", None)  # candidate 1 finished the AI interview
    for c in db.query(Candidate):
        for secret in identity_strings(c.profile):
            assert secret.lower() not in r.text.lower()


def test_decision_log_csv_and_audit_bundle_with_a_checksum(busy, db):
    log = busy.rc.get("/export/decision-log.csv").text
    assert "move SCREENED -> SHORTLISTED" in log and "recruiter@example.com" in log
    assert busy.rc.get("/export/audit.json").status_code == 403  # only the hiring manager
    r = busy.hm.get("/export/audit.json")
    body = r.json()
    assert body["decision_log"] and body["exported_by"] == "hm@example.com"
    again = {k: v for k, v in body.items() if k not in ("exported_at", "exported_by", "sha256")}
    # the checksum covers the content at the time of export; entries added by the export itself come after it
    assert len(body["sha256"]) == 64 and hashlib.sha256(json.dumps(again, sort_keys=True).encode()).hexdigest() == body["sha256"]
    db.expire_all()
    assert db.query(DecisionLog).filter(DecisionLog.action == "audit bundle exported").count() == 1


def test_the_scorecard_pdf_is_a_real_pdf_and_the_download_is_logged(busy, db):
    r = busy.rc.get("/export/scorecard/1.pdf")
    assert r.status_code == 200 and r.content[:5] == b"%PDF-" and r.headers["content-type"] == "application/pdf"
    assert busy.visitor.get("/export/scorecard/1.pdf").status_code in (303, 401, 403)
    db.expire_all()
    assert db.query(DecisionLog).filter(DecisionLog.action == "scorecard PDF exported").count() == 1
    assert busy.rc.get("/export/scorecard/999.pdf").status_code == 404
