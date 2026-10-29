"""Day 2 prompt 7: the invitation (a person, with a reason), the notice, recording consent and asking for a person."""
import pytest

from app.models import Candidate, DecisionLog
from app.models_ext import InterviewSession
from tests.test_interview import shortlisted, token  # noqa: F401  (fixtures and helper of the interview tests)


def test_only_a_recruiter_can_invite_and_a_reason_is_required(shortlisted, db):
    assert shortlisted.hm.post("/interviews/1/invite", data={"reason": "x"}).status_code == 403
    shortlisted.rc.post("/interviews/1/invite", data={"reason": "  "})
    db.expire_all()
    assert db.get(Candidate, 1).stage == "SHORTLISTED"  # refused: no reason
    shortlisted.rc.post("/interviews/1/invite", data={"reason": "best evidence on the must-haves"})
    db.expire_all()
    assert db.get(Candidate, 1).stage == "AI_INTERVIEW"
    log = db.query(DecisionLog).filter(DecisionLog.action == "move SHORTLISTED -> AI_INTERVIEW").one()
    assert log.actor == "recruiter@example.com" and log.reason == "best evidence on the must-haves"
    iv = db.query(InterviewSession).one()  # the interview record is made at the invitation, with its plan
    assert iv.id == 1 and iv.candidate_id == 1 and iv.plan and iv.status == "NOT_STARTED" and not iv.consent_recording


def test_the_candidates_page_shows_the_notice_the_tick_box_and_both_buttons(shortlisted, db):
    shortlisted.rc.post("/interviews/1/invite", data={"reason": "invited"})
    page = shortlisted.visitor.get(f"/me/{token(db)}").text
    for needle in ("about 25 minutes", "by voice", "diagram", "never your voice, accent or how you speak", "recorded", "hiring manager and the recruiters",
                   "deleted after", "A recruiter reviews every interview", "I understand the interview is recorded", "Start my interview",
                   "I would like to speak to a person instead"):
        assert needle in page, needle


def test_starting_without_the_consent_tick_is_refused_everywhere(shortlisted, db):
    shortlisted.rc.post("/interviews/1/invite", data={"reason": "invited"})
    t = token(db)
    r = shortlisted.visitor.post(f"/me/{t}/interview/start", data={})
    assert r.status_code == 400 and "tick the box" in r.text
    assert shortlisted.visitor.post(f"/interview/{t}/notice").status_code == 400  # the server checks it, not only the page
    assert shortlisted.visitor.post(f"/interview/{t}/start").status_code == 409
    db.expire_all()
    assert not db.query(InterviewSession).one().consent_recording


def test_ticking_the_box_records_consent_and_opens_the_interview_page(shortlisted, db):
    shortlisted.rc.post("/interviews/1/invite", data={"reason": "invited"})
    t = token(db)
    r = shortlisted.visitor.post(f"/me/{t}/interview/start", data={"agree": "yes"})
    assert r.status_code == 303 and r.headers["location"] == f"/interview/{t}"
    db.expire_all()
    iv = db.query(InterviewSession).one()
    assert iv.consent_recording and iv.consent_at is not None
    assert "recording consent" in " ".join(e.reason for e in db.query(DecisionLog)) or "agreed to the interview being recorded" in " ".join(e.reason for e in db.query(DecisionLog))
    assert shortlisted.visitor.post(f"/interview/{t}/start").status_code == 200


def test_asking_for_a_person_is_logged_flagged_on_the_board_and_changes_no_score(shortlisted, db):
    shortlisted.rc.post("/interviews/1/invite", data={"reason": "invited"})
    t = token(db)
    assert shortlisted.visitor.post(f"/me/{t}/interview/person").status_code == 303
    db.expire_all()
    iv = db.query(InterviewSession).one()
    assert iv.status == "PERSON_REQUESTED" and iv.person_requested_at is not None and iv.scorecard is None
    log = db.query(DecisionLog).filter(DecisionLog.action == "asked for a person").one()
    assert log.evidence == {"asked_for_person": True} and "never counted against" in log.reason
    assert "asked for a person" in shortlisted.rc.get("/pipeline").text
    assert "You asked to speak to a person" in shortlisted.visitor.get(f"/me/{t}").text
