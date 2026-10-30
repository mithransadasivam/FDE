"""Day 4 prompt 1: one scorecard per candidate: three stages side by side, every quote verified, play links with the right time, blind for the hiring manager."""
import re

import pytest

from app.interview import recording
from app.models import Candidate, DecisionLog, Requisition
from app.models_ext import InterviewSession
from app.stages import stage_summary
from tests.sim.runner import run_interview
from tests.test_browser import browser, live  # noqa: F401
from tests.test_interview import invited, review_form, shortlisted, token  # noqa: F401


@pytest.fixture
def done(invited, db):
    run_interview(db, db.get(Candidate, 1), db.get(Requisition, 1), "strong")
    db.expire_all()
    invited.rc.post("/interviews/1/review", data=review_form(db))
    return invited


def test_the_scorecard_lives_under_the_candidate_and_opening_it_is_logged(done, db):
    a = done.rc.get("/candidates/1/scorecard")
    b = done.rc.get("/scorecard/1")
    assert a.status_code == 200 and b.status_code == 200 and "The three stages side by side" in a.text
    db.expire_all()
    assert db.query(DecisionLog).filter(DecisionLog.action == "scorecard opened").count() == 2


def test_the_summary_has_one_row_per_rubric_skill_with_the_three_stages(done, db):
    cand = db.get(Candidate, 1)
    rows = stage_summary(db, cand)["rows"]
    skills = [i["skill"] for i in db.get(Requisition, 1).rubric["items"]]
    assert [r["skill"] for r in rows] == skills
    assert any(r["screening"] is not None for r in rows) and any(r["ai"] is not None for r in rows)
    html = done.rc.get("/candidates/1/scorecard").text
    for sk in skills:
        assert f'data-skill="{sk}"' in html


def test_every_quote_shown_is_verified_and_the_play_link_carries_the_right_time(done, db):
    s = db.query(InterviewSession).one()
    timeline = recording.load_timeline(s)
    rows = stage_summary(db, db.get(Candidate, 1))["rows"]
    linked = [r for r in rows if r["ai_quote"]]
    assert linked
    for r in linked:
        line = next(c for c in timeline["clips"] if c["speaker"] == "candidate" and recording.moment_time({"clips": [c]}, r["ai_quote"]) is not None)
        assert r["ai_play_t"] == round(max(0.0, line["start"] - 1.0), 1)  # the line's start minus one second
    for r in rows:
        if r["cv_quote"]:
            assert r["cv_verified"]
    html = done.rc.get("/candidates/1/scorecard").text
    times = re.findall(r'/interviews/1/replay\?t=([\d.]+)', html)
    assert times and set(times) == {str(r["ai_play_t"]) for r in linked if r["ai_play_t"] is not None}


def test_the_replay_page_reads_t_from_the_link(done):
    html = done.rc.get("/interviews/1/replay?t=12.5").text
    assert 'URLSearchParams(location.search).get("t")' in html and "loadedmetadata" in html


def test_the_hiring_manager_sees_no_identity_and_no_play_links(done, db):
    html = done.hm.get("/candidates/1/scorecard").text
    cand = db.get(Candidate, 1)
    for secret in (cand.profile["name"]["value"], cand.profile["email"]["value"]):
        assert secret not in html
    assert "play this moment" not in html  # audio is for the recruiter
    assert done.visitor.get("/candidates/1/scorecard").status_code in (303, 401, 403)


def test_the_page_can_be_saved_as_pdf(done):
    html = done.rc.get("/candidates/1/scorecard").text
    assert "@media print" in html and "Download as PDF" in html


def test_a_quote_that_is_not_in_the_recording_gets_no_time():
    tl = {"clips": [{"speaker": "candidate", "start": 10.0, "end": 20.0, "text": "We used a load balancer."}]}
    assert recording.moment_time(tl, "We used a LOAD balancer") == 9.0
    assert recording.moment_time(tl, "something never said") is None
    assert recording.moment_time({"clips": [{"speaker": "interviewer", "start": 3, "text": "a load balancer"}]}, "a load balancer") is None
