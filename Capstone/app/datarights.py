"""A candidate's data rights: a copy of what we hold, and erasure. (Product feature; supports GDPR-style access and erasure requests.)

A copy is produced at once from the candidate's private link. ERASURE is a person's decision (rule 1): the candidate asks, a recruiter approves or refuses with a reason,
and only then is personal data deleted. What stays is the accountability trail: the decision log keeps WHAT happened and WHO decided, but its evidence (which can hold CV
quotes) is removed, so no personal data remains there.
"""
import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Candidate, DecisionLog, ReviewItem
from app.models_ext import (CvText, DataRequest, EmailDraft, Flag, HumanInterview, InterviewSession, InterviewTurn, ItemScoreRow, ShortlistEntry)
from app.schemas import Stage
from app.supervisor import MoveRefused, move

RIGHTS = ["Ask for a person instead of the AI interviewer, at any time.", "Ask for an explanation of how your application was assessed.",
          "Download a copy of the data we hold about you (this file).", "Ask for your data to be deleted. A recruiter decides, and tells you the reason if the answer is no."]


def export_data(db: Session, cand: Candidate) -> dict:
    """Everything we hold about the candidate, in plain words, for the candidate."""
    profile = {k: (v or {}).get("value") for k, v in (cand.profile or {}).items()}
    history = []
    for e in db.scalars(select(DecisionLog).where(DecisionLog.subject == f"candidate:{cand.id}", DecisionLog.action.like("move %")).order_by(DecisionLog.id)):
        a, b = e.action[5:].split(" -> ")
        history.append({"at": e.at.isoformat() if e.at else None, "from": a, "to": b})
    s = db.scalars(select(InterviewSession).where(InterviewSession.candidate_id == cand.id)).first()
    interview = None
    if s and s.state:
        qa = []
        for t in s.state.get("turns", []):
            answers = list(t.get("answers", []))
            for m in t.get("meta", []):
                if m["kind"] != "hint":
                    qa.append({"question": m["text"], "your_answer": (answers.pop(0)["text"] if answers else "")})
        interview = {"status": s.status, "questions_and_answers": qa, "recorded": bool(s.consent_recording),
                     "recording_kept_for_days": get_settings().retention_days}
    return {
        "about_this_file": "This is the data the hiring platform holds about you. It was produced from your private link.",
        "application": {"candidate_number": cand.id, "applied_at": cand.applied_at.isoformat() if cand.applied_at else None, "current_stage": cand.stage,
                        "agreed_to_ai_use": bool(cand.consent_ai), "cv_file_name": cand.cv_name},
        "details_read_from_your_cv": profile,
        "stage_history": history,
        "cv_scores": [{"skill": r.skill, "score_out_of_3": r.score, "quote_from_your_cv": r.quote}
                      for r in db.scalars(select(ItemScoreRow).where(ItemScoreRow.candidate_id == cand.id).order_by(ItemScoreRow.id))],
        "ai_interview": interview,
        "emails_about_you": [{"kind": d.kind, "subject": d.subject, "status": d.status} for d in db.scalars(select(EmailDraft).where(EmailDraft.candidate_id == cand.id))],
        "your_rights": RIGHTS,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def open_delete_request(db: Session, cand: Candidate) -> DataRequest:
    if cand.erased_at:
        raise MoveRefused("Your personal data has already been erased.")
    existing = db.scalars(select(DataRequest).where(DataRequest.candidate_id == cand.id, DataRequest.kind == "delete", DataRequest.status == "REQUESTED")).first()
    if existing:
        return existing
    req = DataRequest(candidate_id=cand.id, kind="delete")
    db.add(req)
    db.add(DecisionLog(actor="candidate", action="asked for their data to be deleted", subject=f"candidate:{cand.id}", reason="a recruiter will decide; nothing is erased automatically"))
    db.flush()
    return req


def erase(db: Session, cand: Candidate, req: DataRequest, actor: str, reason: str) -> None:
    """Deletes the candidate's personal data. Only called after a person approved the request."""
    if "@" not in (actor or ""):
        raise MoveRefused("Only a person can approve an erasure.")
    if not (reason or "").strip():
        raise MoveRefused("An erasure needs a reason on record.")
    storage = get_settings().storage_dir
    if cand.cv_path:
        Path(cand.cv_path).unlink(missing_ok=True)
    s = db.scalars(select(InterviewSession).where(InterviewSession.candidate_id == cand.id)).first()
    if s:
        shutil.rmtree(storage / "interviews" / str(s.id), ignore_errors=True)
        db.execute(delete(InterviewTurn).where(InterviewTurn.interview_id == s.id))
        db.delete(s)
    for model in (CvText, Flag, ReviewItem, ItemScoreRow, ShortlistEntry, HumanInterview):
        col = model.candidate_id
        db.execute(delete(model).where(col == cand.id))
    for d in db.scalars(select(EmailDraft).where(EmailDraft.candidate_id == cand.id)):
        d.body = "[erased at the candidate's request]"
    for e in db.scalars(select(DecisionLog).where(DecisionLog.subject == f"candidate:{cand.id}")):
        e.evidence = None  # the log keeps what happened and who decided; the evidence (which can hold CV quotes) goes
    if cand.stage != Stage.WITHDRAWN.value:
        move(db, cand, Stage.WITHDRAWN, actor, f"data erasure approved: {reason.strip()}")
    cand.profile, cand.cv_path, cand.cv_name, cand.erased_at = None, "", "[erased]", datetime.now(timezone.utc)
    req.status, req.decided_by, req.decided_at, req.reason = "DONE", actor, datetime.now(timezone.utc), reason.strip()
    db.add(DecisionLog(actor=actor, action="personal data erased", subject=f"candidate:{cand.id}", reason=reason.strip(), evidence={"request_id": req.id}))


def refuse(db: Session, cand: Candidate, req: DataRequest, actor: str, reason: str) -> None:
    if not (reason or "").strip():
        raise MoveRefused("Say why the request is refused: the candidate is told the reason.")
    req.status, req.decided_by, req.decided_at, req.reason = "REFUSED", actor, datetime.now(timezone.utc), reason.strip()
    db.add(DecisionLog(actor=actor, action="erasure request refused", subject=f"candidate:{cand.id}", reason=reason.strip()))
