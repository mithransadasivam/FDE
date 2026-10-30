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
from app.models_ext import (CvText, DataRequest, EmailDraft, EvidenceCheck, ExplanationRequest, FinalDecision, Flag, HumanInterview, HumanInterviewScore, InterviewSession,
                            InterviewTurn, ItemScoreRow, ShortlistEntry)
from app.schemas import Stage
from app.supervisor import MoveRefused, move

RIGHTS = ["Ask for a person instead of the AI interviewer, at any time.", "Ask for an explanation of how your application was assessed.",
          "Download a copy of the data we hold about you (this file).", "Delete your application and your data whenever you like: you confirm, and it is deleted at once."]


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
    ai_stages = stages_with_ai(db, cand, history, bool(s and s.status == "DONE"))
    human = db.scalars(select(HumanInterview).where(HumanInterview.candidate_id == cand.id, HumanInterview.source == "live").order_by(HumanInterview.id.desc())).first()
    return {
        "about_this_file": "This is the data the hiring platform holds about you. It was produced from your private link.",
        "application": {"candidate_number": cand.id, "applied_at": cand.applied_at.isoformat() if cand.applied_at else None, "current_stage": cand.stage,
                        "agreed_to_ai_use": bool(cand.consent_ai), "cv_file_name": cand.cv_name},
        "details_read_from_your_cv": profile,
        "stage_history": history,
        "ai_used_at_each_stage": ai_stages,
        "human_interview_transcript": [{"speaker": ln.get("speaker"), "text": ln.get("text")} for ln in (human.lines or [])] if human else [],
        "cv_scores": [{"skill": r.skill, "score_out_of_3": r.score, "quote_from_your_cv": r.quote}
                      for r in db.scalars(select(ItemScoreRow).where(ItemScoreRow.candidate_id == cand.id).order_by(ItemScoreRow.id))],
        "ai_interview": interview,
        "emails_about_you": [{"kind": d.kind, "subject": d.subject, "status": d.status} for d in db.scalars(select(EmailDraft).where(EmailDraft.candidate_id == cand.id))],
        "your_rights": RIGHTS,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


STAGE_AI = {  # what the AI does at each stage, in plain words (and who decides)
    "APPLIED": (True, "An AI system read your CV and turned it into the details shown above. A person can correct them."),
    "REVIEW": (False, "A person checked the details the AI was not sure about."),
    "EXTRACTED": (True, "Your identity was hidden, so that only skills and experience were seen when scoring."),
    "SCREENED": (True, "An AI system scored your CV against each skill for the role, with a quote from your CV. A recruiter decides who is shortlisted."),
    "SHORTLISTED": (False, "A recruiter chose to shortlist you. No AI made this decision."),
    "AI_INTERVIEW": (True, "An AI interviewer asked you questions and scored what you said (never your voice or accent). A recruiter reviews every interview."),
    "HUMAN_INTERVIEW": (True, "A recruiter interviewed you. An AI assistant may have suggested questions and followed the key points; the recruiter scored and decided."),
    "DECISION": (False, "A recruiter made the decision. No AI made it."),
    "WITHDRAWN": (False, "Your application was withdrawn or your data was deleted."),
}


def stages_with_ai(db: Session, cand: Candidate, history: list[dict], interviewed: bool) -> list[dict]:
    """Every stage the application reached, when, and whether AI was used there (in plain words)."""
    out = [{"stage": "APPLIED", "at": cand.applied_at.isoformat() if cand.applied_at else None}] + [{"stage": h["to"], "at": h["at"]} for h in history]
    seen, rows = set(), []
    for r in out:
        if r["stage"] in seen:
            continue
        seen.add(r["stage"])
        ai, text = STAGE_AI.get(r["stage"], (False, ""))
        rows.append({"stage": r["stage"], "at": r["at"], "ai_used": ai, "what_happened": text})
    return rows


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


def _inside_storage(path: str | Path) -> Path | None:
    """A path is only ever deleted if it is inside the platform's own storage folder (the starter kit's recordings are never touched)."""
    if not path:
        return None
    p = Path(path)
    p = p if p.is_absolute() else Path.cwd() / p
    try:
        p.resolve().relative_to(get_settings().storage_dir.resolve())
    except ValueError:
        return None
    return p


def purge_candidate(db: Session, cand: Candidate, actor: str, why: str) -> dict:
    """Deletes everything personal about a candidate: the CV file, the interview recordings and transcripts, the copilot sessions, the profile, the scores, the
    flags and the email text. What stays is anonymous: the decision log keeps WHAT happened, WHEN and WHO decided (its reasons and evidence, which can quote the CV, are
    removed) and one new line saying the candidate deleted their data. Returns what was removed, so a test or a person can check."""
    storage = get_settings().storage_dir
    removed = {"files": [], "folders": []}
    for f in (_inside_storage(cand.cv_path),):
        if f is not None and f.exists():
            f.unlink()
            removed["files"].append(str(f))
    s = db.scalars(select(InterviewSession).where(InterviewSession.candidate_id == cand.id)).first()
    folders = [storage / "practice" / str(cand.id)]
    if s:
        folders.append(storage / "interviews" / str(s.id))
        db.execute(delete(InterviewTurn).where(InterviewTurn.interview_id == s.id))
        db.delete(s)
    for h in db.scalars(select(HumanInterview).where(HumanInterview.candidate_id == cand.id)):
        rec = _inside_storage(h.recording)
        if rec is not None and rec.exists():
            rec.unlink()
            removed["files"].append(str(rec))
    drafts = list(db.scalars(select(EmailDraft).where(EmailDraft.candidate_id == cand.id)))
    for d in drafts:
        for eml in (storage / "outbox_sent").glob(f"draft_{d.id:05d}*.eml"):  # the saved copy of an approved email
            eml.unlink(missing_ok=True)
            removed["files"].append(str(eml))
        d.body, d.subject = "[erased at the candidate's request]", "[erased]"
    for folder in folders:
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
            removed["folders"].append(str(folder))
    for model in (CvText, Flag, ReviewItem, ItemScoreRow, ShortlistEntry, HumanInterview, HumanInterviewScore, EvidenceCheck, ExplanationRequest):
        db.execute(delete(model).where(model.candidate_id == cand.id))
    for fd in db.scalars(select(FinalDecision).where(FinalDecision.candidate_id == cand.id)):
        fd.evidence, fd.reason = None, "[removed when the candidate deleted their data]"
    for e in db.scalars(select(DecisionLog).where(DecisionLog.subject == f"candidate:{cand.id}")):
        e.evidence, e.reason = None, "[removed when the candidate deleted their data]"  # what happened and who decided stay; the words about the person go
    if cand.stage != Stage.WITHDRAWN.value:
        move(db, cand, Stage.WITHDRAWN, actor, why)
    cand.profile, cand.cv_path, cand.cv_name, cand.erased_at = None, "", "[erased]", datetime.now(timezone.utc)
    return removed


def erase(db: Session, cand: Candidate, req: DataRequest, actor: str, reason: str) -> None:
    """A recruiter approved a request to erase (the older, reviewed route)."""
    if "@" not in (actor or ""):
        raise MoveRefused("Only a person can approve an erasure.")
    if not (reason or "").strip():
        raise MoveRefused("An erasure needs a reason on record.")
    purge_candidate(db, cand, actor, f"data erasure approved: {reason.strip()}")
    req.status, req.decided_by, req.decided_at, req.reason = "DONE", actor, datetime.now(timezone.utc), reason.strip()
    db.add(DecisionLog(actor=actor, action="personal data erased", subject=f"candidate:{cand.id}", reason=reason.strip(), evidence={"request_id": req.id}))


def delete_my_application(db: Session, cand: Candidate) -> DataRequest:
    """The candidate deleted their own application (Day 4, prompt 6): after they confirmed, everything personal is removed at once and the candidate is WITHDRAWN.
    The decision log gets one anonymous line, and a finished request is recorded so recruiters can see it happened."""
    if cand.erased_at:
        raise MoveRefused("Your personal data has already been deleted.")
    today = datetime.now(timezone.utc).date().isoformat()
    removed = purge_candidate(db, cand, "candidate", "the candidate deleted their own application")
    req = DataRequest(candidate_id=cand.id, kind="delete", status="DONE", decided_by="candidate (self-service)", decided_at=datetime.now(timezone.utc),
                      reason="the candidate confirmed and deleted their own data")
    db.add(req)
    db.add(DecisionLog(actor="candidate", action="candidate deleted their data", subject=f"candidate:{cand.id}", reason=f"candidate {cand.id} deleted their data on {today}",
                       evidence={"files_removed": len(removed["files"]), "folders_removed": len(removed["folders"])}))
    return req


def refuse(db: Session, cand: Candidate, req: DataRequest, actor: str, reason: str) -> None:
    if not (reason or "").strip():
        raise MoveRefused("Say why the request is refused: the candidate is told the reason.")
    req.status, req.decided_by, req.decided_at, req.reason = "REFUSED", actor, datetime.now(timezone.utc), reason.strip()
    db.add(DecisionLog(actor=actor, action="erasure request refused", subject=f"candidate:{cand.id}", reason=reason.strip()))
