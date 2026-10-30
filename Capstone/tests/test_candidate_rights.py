"""Day 4 prompt 6: a candidate can see their data, delete their application (files and personal fields, one anonymous line stays) and ask why they were not shortlisted."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import get_settings
from app.models import Candidate, DecisionLog, Requisition
from app.models_ext import (CvText, DataRequest, EmailDraft, ExplanationRequest, FinalDecision, Flag, HumanInterview, InterviewSession, ItemScoreRow, OutboxLog)
from app.practice import make_practice
from tests.sim.runner import run_interview
from tests.test_interview import invited, shortlisted, token  # noqa: F401
from scripts.purge_recordings import GONE, purge


def _all_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


@pytest.fixture
def rich(invited, db):
    """Candidate 1 has an interview with recordings, a practice interview, a copilot session and an approved email on disk."""
    run_interview(db, db.get(Candidate, 1), db.get(Requisition, 1), "strong")
    make_practice(db, db.get(Candidate, 1), speak_real=False)
    db.add(HumanInterview(candidate_id=1, recording="", notice_ack=True, status="DONE", source="practice", lines=[{"speaker": "candidate", "text": "I use Terraform"}], events=[]))
    db.commit()
    invited.rc.post("/outbox/1/approve")  # writes storage/outbox_sent/draft_00001.eml
    db.expire_all()
    return invited


# ---- 1. see my data ---------------------------------------------------------------------------------------------------------------------------
def test_see_my_data_shows_profile_stages_ai_use_and_the_transcript(rich, db):
    t = token(db)
    html = rich.visitor.get(f"/me/{t}/my-data").text
    cand = db.get(Candidate, 1)
    assert cand.profile["name"]["value"] in html and "What we read from your CV" in html
    assert 'data-testid="stages"' in html and "AI helped" in html and "a person" in html  # AI use is said at each stage
    assert "Your AI interview" in html and 'data-testid="transcript"' in html and "You:" in html
    db.expire_all()
    assert db.query(DecisionLog).filter(DecisionLog.action == "data viewed").count() == 1


def test_see_my_data_never_shows_other_candidates_or_internal_notes(rich, db):
    db.add(Flag(candidate_id=1, kind="internal note for recruiters", detail="SECRET-INTERNAL-NOTE"))
    db.commit()
    html = rich.visitor.get(f"/me/{token(db)}/my-data").text
    others = [db.get(Candidate, i).profile["name"]["value"] for i in (2, 3)]
    assert all(o not in html for o in others) and "SECRET-INTERNAL-NOTE" not in html and "internal note for recruiters" not in html
    assert "recommendation" not in html.lower() and "second scorer" not in html.lower()
    assert rich.visitor.get("/me/not-a-token/my-data").status_code == 404


# ---- 2. delete my application -----------------------------------------------------------------------------------------------------------------
def test_the_delete_page_explains_and_nothing_is_deleted_without_the_confirmation(rich, db):
    t = token(db)
    page = rich.visitor.get(f"/me/{t}/delete").text
    assert "cannot be undone" in page and "WITHDRAWN" in page and 'data-testid="confirm-box"' in page
    r = rich.visitor.post(f"/me/{t}/delete", data={})
    assert r.status_code == 200 and "Nothing has been deleted" in r.text
    db.expire_all()
    assert db.get(Candidate, 1).profile and db.get(Candidate, 1).erased_at is None


def test_deleting_removes_every_file_and_personal_field(rich, db):
    cand = db.get(Candidate, 1)
    name, email = cand.profile["name"]["value"], cand.profile["email"]["value"]
    cv = Path(cand.cv_path)
    storage = get_settings().storage_dir
    others_cv = Path(db.get(Candidate, 2).cv_path)
    assert cv.exists() and (storage / "interviews" / "1").exists() and (storage / "practice" / "1").exists() and list((storage / "outbox_sent").glob("draft_00001*"))
    t = token(db)
    r = rich.visitor.post(f"/me/{t}/delete", data={"confirm": "yes"})
    assert r.status_code == 303 and r.headers["location"] == f"/me/{t}?deleted=1"
    db.expire_all()
    cand = db.get(Candidate, 1)
    # files: the CV, the interview recordings and transcripts, the practice interview, the saved email
    assert not cv.exists() and not (storage / "interviews" / "1").exists() and not (storage / "practice" / "1").exists() and not list((storage / "outbox_sent").glob("draft_00001*"))
    assert others_cv.exists() and (storage / "cvs").exists()  # nobody else is touched
    # personal fields
    assert cand.profile is None and cand.cv_path == "" and cand.cv_name == "[erased]" and cand.erased_at and cand.stage == "WITHDRAWN"
    for model in (CvText, ItemScoreRow, InterviewSession, HumanInterview, Flag, ExplanationRequest):
        assert db.query(model).filter_by(candidate_id=1).count() == 0, model
    assert all("erased" in (d.body or "") for d in db.query(EmailDraft).filter_by(candidate_id=1))
    # nothing left in the storage folder that names them
    for f in _all_files(storage):
        if f.suffix in (".eml", ".json", ".txt"):
            text = f.read_text(encoding="utf-8", errors="ignore")
            assert name not in text and email not in text, f
    assert db.get(Candidate, 2).profile  # others keep theirs


def test_the_decision_log_keeps_only_an_anonymous_trail(rich, db):
    cand = db.get(Candidate, 1)
    name, email = cand.profile["name"]["value"], cand.profile["email"]["value"]
    db.add(FinalDecision(candidate_id=1, decision="HOLD", reason=f"{name} was strong on Linux", actor="recruiter@example.com", evidence={"quote": "I ran Kubernetes at Acme"}))
    db.commit()
    rich.visitor.post(f"/me/{token(db)}/delete", data={"confirm": "yes"})
    db.expire_all()
    mine = [e for e in db.query(DecisionLog) if e.subject == "candidate:1"]
    today = datetime.now(timezone.utc).date().isoformat()
    line = [e for e in mine if e.action == "candidate deleted their data"]
    assert len(line) == 1 and line[0].reason == f"candidate 1 deleted their data on {today}" and line[0].actor == "candidate"
    blob = json.dumps([[e.action, e.reason, e.evidence] for e in mine], default=str)
    assert name not in blob and email not in blob and "Kubernetes at Acme" not in blob and "strong on Linux" not in blob
    assert any(e.action.startswith("move ") and e.action.endswith("-> WITHDRAWN") for e in mine)  # who moved it, and when, stays
    fd = db.query(FinalDecision).filter_by(candidate_id=1).one()
    assert fd.evidence is None and name not in fd.reason
    done = db.query(DataRequest).filter_by(candidate_id=1, kind="delete").one()
    assert done.status == "DONE" and done.decided_by == "candidate (self-service)"


def test_staff_see_withdrawn_and_the_candidate_sees_that_it_is_done(rich, db):
    t = token(db)
    rich.visitor.post(f"/me/{t}/delete", data={"confirm": "yes"})
    assert "WITHDRAWN" in rich.rc.get("/candidates").text
    page = rich.visitor.get(f"/me/{t}?deleted=1").text
    assert "Your application has been deleted" in page and 'data-testid="erased"' in page and 'data-testid="delete-application"' not in page
    assert rich.visitor.get(f"/me/{t}/my-data").status_code == 303  # nothing left to show
    assert rich.visitor.get(f"/me/{t}/data.json").status_code == 410
    again = rich.visitor.post(f"/me/{t}/delete", data={"confirm": "yes"})
    assert again.status_code == 303
    db.expire_all()
    assert db.query(DecisionLog).filter(DecisionLog.action == "candidate deleted their data").count() == 1  # deleting twice leaves one line


# ---- 3. why was I not shortlisted? ------------------------------------------------------------------------------------------------------------
@pytest.fixture
def not_shortlisted(shortlisted, db):
    """Candidate 2 was screened but not shortlisted (candidates 1 and 3 were)."""
    shortlisted.rc.post("/screening/1/run")
    return shortlisted


def _screened_not_shortlisted(db) -> Candidate:
    return next(c for c in db.query(Candidate).order_by(Candidate.id) if c.stage == "SCREENED")


def test_the_explanation_is_drafted_from_their_own_evidence_and_waits_for_a_person(platform, db):
    for f in ("C-001_cv.pdf", "C-004_cv.docx", "C-007_cv.pdf", "C-011_cv.docx"):
        platform.apply(f)
    platform.rc.post("/screening/1/run")
    platform.rc.post("/screening/1/approve", data={"reason": "best two", "candidate_id": [1, 3]})
    db.expire_all()
    cand = _screened_not_shortlisted(db)
    t = cand.access_token
    page = platform.visitor.get(f"/me/{t}").text
    assert "Why was I not shortlisted?" in page and "never compare you with other people" in page
    r = platform.visitor.post(f"/me/{t}/explain")
    assert r.status_code == 303
    assert "A person will reply within 5 working days" in platform.visitor.get(f"/me/{t}?explain=asked").text
    db.expire_all()
    draft = db.get(EmailDraft, db.query(ExplanationRequest).one().draft_id)
    others = [c.profile["name"]["value"] for c in db.query(Candidate) if c.id != cand.id]
    body = draft.body
    assert draft.kind == "explanation" and draft.status == "DRAFT" and db.query(OutboxLog).count() == 0  # not sent
    assert all(n not in body for n in others) and "other candidate" not in body.lower() and "other applicant" not in body.lower() and "ranked" not in body.lower()
    for word in ("age", "gender", "religion", "nationality", "married", "pregnan"):
        assert f" {word} " not in body.lower()
    assert "evidence" in body.lower() and "recruiter" in body.lower()


def test_the_explanation_names_must_have_skills_with_no_evidence_and_what_the_job_asked_for(platform, db):
    for f in ("C-001_cv.pdf", "C-004_cv.docx", "C-007_cv.pdf", "C-011_cv.docx", "C-013_cv.pdf"):
        platform.apply(f)
    platform.rc.post("/screening/1/run")
    platform.rc.post("/screening/1/approve", data={"reason": "top", "candidate_id": [1]})
    db.expire_all()
    req = db.get(Requisition, 1)
    musts = {i["skill"] for i in req.rubric["items"] if i.get("must_have")}
    found = None
    for c in db.query(Candidate).filter(Candidate.stage == "SCREENED"):
        zero = {r.skill for r in db.query(ItemScoreRow).filter_by(candidate_id=c.id) if r.score == 0} & musts
        if zero:
            found = (c, zero)
            break
    if found is None:
        pytest.skip("every screened candidate had evidence for every must-have")
    cand, zero = found
    platform.visitor.post(f"/me/{cand.access_token}/explain")
    db.expire_all()
    body = db.get(EmailDraft, db.query(ExplanationRequest).one().draft_id).body
    assert all(skill in body for skill in list(zero)[:3]) and "the role asks for" in body


def test_a_shortlisted_candidate_cannot_ask_why_not_shortlisted(shortlisted, db):
    t = token(db, 1)  # candidate 1 was shortlisted
    assert "Why was I not shortlisted?" not in shortlisted.visitor.get(f"/me/{t}").text
    shortlisted.visitor.post(f"/me/{t}/explain")
    db.expire_all()
    assert db.query(ExplanationRequest).count() == 0


# ---- retention: transcripts and CV files older than retention_days ------------------------------------------------------------------------
def test_the_purge_clears_old_transcripts_and_cv_files_but_keeps_the_levels(rich, db):
    cand = db.get(Candidate, 1)
    cv = Path(cand.cv_path)
    s = db.query(InterviewSession).filter_by(candidate_id=1).one()
    before = [a["text"] for t in s.state["turns"] for a in t.get("answers", [])]
    levels = [t["score"]["score"] for t in s.state["turns"] if t.get("score")]
    future = datetime.now(timezone.utc) + timedelta(days=get_settings().retention_days + 5)
    dry = purge(db, now=future, dry_run=True)
    assert dry["transcripts_cleared"] > 0 and dry["cv_files_deleted"] >= 1 and cv.exists() and [a["text"] for t in s.state["turns"] for a in t.get("answers", [])] == before
    out = purge(db, now=future)
    db.expire_all()
    s = db.query(InterviewSession).filter_by(candidate_id=1).one()
    assert out["transcripts_cleared"] > 0 and not cv.exists() and db.get(Candidate, 1).cv_path == ""
    assert all(a["text"] == GONE for t in s.state["turns"] for a in t.get("answers", []))
    assert [t["score"]["score"] for t in s.state["turns"] if t.get("score")] == levels  # the levels stay: the audit trail does
    assert purge(db, now=future)["transcripts_cleared"] == 0  # a second run has nothing more to clear
    assert db.query(DecisionLog).filter(DecisionLog.action == "interview transcript deleted").count() == 1
