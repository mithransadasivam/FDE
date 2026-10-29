"""Day 3 prompt 3: the evidence checker: CHECKED or NEEDS_REVIEW, reports only, and a person must look before the recruiter shortlists or decides."""
import pytest

from app.agents import checker
from app.models import Candidate, DecisionLog, Requisition
from app.models_ext import EvidenceCheck, ItemScoreRow, ShortlistEntry
from app.shortlist import approve_shortlist
from app.supervisor import MoveRefused
from tests.sim.runner import run_interview
from tests.test_interview import invited, review_form, shortlisted, token  # noqa: F401

FILES = ["C-001_cv.pdf", "C-002_cv.pdf", "C-004_cv.docx"]


@pytest.fixture
def screened(platform, db):
    for f in FILES:
        platform.apply(f)
    platform.rc.post("/screening/1/run")
    db.expire_all()
    return platform


def check_of(db, cid, subject="screening"):
    return db.query(EvidenceCheck).filter_by(candidate_id=cid, subject=subject).one()


def test_a_clean_screening_is_checked_and_every_screened_candidate_has_a_status(screened, db):
    assert db.query(EvidenceCheck).filter_by(subject="screening").count() == 3
    for cid in (1, 2, 3):
        assert check_of(db, cid).status == "CHECKED" and check_of(db, cid).items == []
    assert "CHECKED" in screened.rc.get("/screening/1").text


def test_a_reason_that_mentions_a_protected_detail_is_caught():
    for text in ("Strong candidate, a native speaker of English", "Seems young and energetic", "Confident speaker with a clear accent", "Has two children",
                 "Mentions her age", "Good tone of voice"):
        assert checker.protected_hits(text), text
    for fine in ("Listed Linux and Python, five years of experience", "Customer communication with ITIL certification"):
        assert checker.protected_hits(fine) == [], fine


def test_a_protected_word_in_the_quote_or_in_the_strengths_makes_the_candidate_needs_review(screened, db):
    row = db.query(ItemScoreRow).filter_by(candidate_id=1, skill="Linux troubleshooting").one()
    row.quote = "Linux (a native speaker of English)"
    db.commit()
    res = checker.check_screening(db, db.get(Candidate, 1), db.get(Requisition, 1))
    kinds = {p["problem"] for p in res.items}
    assert res.status == "NEEDS_REVIEW" and "protected detail" in kinds and "quote not found" in kinds
    entry = db.query(ShortlistEntry).filter_by(candidate_id=2).one()
    entry.strengths = ["Linux (3/3): strong young engineer"]
    db.commit()
    assert any("young" in p["detail"] for p in checker.check_screening(db, db.get(Candidate, 2), db.get(Requisition, 1)).items)


def test_a_quote_that_does_not_support_a_level_three_is_caught_by_the_model_check(screened, db):
    row = db.query(ItemScoreRow).filter_by(candidate_id=1, skill="Terraform").one()
    row.score, row.quote = 3, "ITIL 4 Foundation"  # a real line of the CV, but about something else
    db.commit()
    res = checker.check_screening(db, db.get(Candidate, 1), db.get(Requisition, 1))
    problems = [p for p in res.items if p["problem"] == "quote does not support the level"]
    assert res.status == "NEEDS_REVIEW" and problems and problems[0]["where"] == "Terraform"


def test_totals_that_do_not_add_up_are_caught(screened, db):
    db.query(ShortlistEntry).filter_by(candidate_id=3).one().weighted_total = 99.0
    db.commit()
    res = checker.check_screening(db, db.get(Candidate, 3), db.get(Requisition, 1))
    assert any(p["problem"] == "totals do not add up" for p in res.items)


def test_the_checker_reports_and_never_changes_a_score(screened, db):
    row = db.query(ItemScoreRow).filter_by(candidate_id=1, skill="Terraform").one()
    row.score, row.quote = 3, "ITIL 4 Foundation"
    db.commit()
    before = [(r.skill, r.score, r.quote) for r in db.query(ItemScoreRow).order_by(ItemScoreRow.id)]
    checker.check_screening(db, db.get(Candidate, 1), db.get(Requisition, 1))
    db.commit()
    assert [(r.skill, r.score, r.quote) for r in db.query(ItemScoreRow).order_by(ItemScoreRow.id)] == before


def test_shortlisting_waits_for_the_tick_and_the_tick_is_a_persons_action(screened, db):
    row = db.query(ItemScoreRow).filter_by(candidate_id=1, skill="Terraform").one()
    row.score, row.quote = 3, "ITIL 4 Foundation"
    db.commit()
    checker.check_screening(db, db.get(Candidate, 1), db.get(Requisition, 1))
    db.commit()
    assert "NEEDS_REVIEW" in screened.rc.get("/screening/1").text and "I have looked at these" in screened.rc.get("/screening/1").text
    screened.rc.post("/screening/1/approve", data={"reason": "best evidence", "candidate_id": [1, 2]})
    db.expire_all()
    assert db.get(Candidate, 1).stage == "SCREENED"  # refused until someone has looked
    with pytest.raises(MoveRefused, match="looked at these"):
        approve_shortlist(db, 1, [1], "recruiter@example.com", "x")
    db.rollback()
    ck = check_of(db, 1)
    assert screened.hm.post(f"/screening/checks/{ck.id}/ack", data={}).status_code == 403  # the recruiter does this
    with pytest.raises(PermissionError):
        checker.acknowledge(db, ck.id, "system")
    screened.rc.post(f"/screening/checks/{ck.id}/ack", data={"back": "/screening/1"})
    db.expire_all()
    assert check_of(db, 1).acknowledged_by == "recruiter@example.com"
    assert db.query(DecisionLog).filter(DecisionLog.action == "evidence problems acknowledged").one().actor == "recruiter@example.com"
    screened.rc.post("/screening/1/approve", data={"reason": "best evidence", "candidate_id": [1, 2]})
    db.expire_all()
    assert db.get(Candidate, 1).stage == "SHORTLISTED"


def test_an_interview_scorecard_is_checked_too_and_the_decision_waits_for_the_tick(invited, db):
    run_interview(db, db.get(Candidate, 1), db.get(Requisition, 1), "strong")
    db.expire_all()
    assert check_of(db, 1, "interview").status == "CHECKED" and "CHECKED" in invited.rc.get("/interviews/1").text
    s = db.query(__import__("app.models_ext", fromlist=["InterviewSession"]).InterviewSession).one()
    s.scorecard["summary"]["text"] = "A confident speaker with a lovely accent."
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(s, "scorecard")
    db.commit()
    res = checker.check_interview(db, s)
    db.commit()
    assert res.status == "NEEDS_REVIEW" and any(p["where"] == "summary" for p in res.items)
    assert "evidence-box" in invited.rc.get("/interviews/1").text
    invited.rc.post("/interviews/1/review", data=review_form(db))
    invited.rc.post("/interviews/1/decision", data={"decision": "human_interview", "reason": "strong"})
    db.expire_all()
    assert db.get(Candidate, 1).stage == "AI_INTERVIEW"  # waiting for the tick
    invited.rc.post(f"/screening/checks/{res.id}/ack", data={"back": "/interviews/1"})
    invited.rc.post("/interviews/1/decision", data={"decision": "human_interview", "reason": "strong"})
    db.expire_all()
    assert db.get(Candidate, 1).stage == "HUMAN_INTERVIEW"
