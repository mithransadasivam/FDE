"""The interview copilot panel (recruiter only): replays a recorded interview as if live and streams what the copilot sees."""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.copilot import CopilotAgent
from app.auth import RECRUITER
from app.config import get_settings
from app.db import SessionLocal, get_db
from app.models import Candidate, DecisionLog, Requisition, User
from app.models_ext import HumanInterview, InterviewSession
from app.schemas import Stage
from app.supervisor import MoveRefused, move
from app.voice.replayer import get_interview, load_interviews, replay
from app.web.common import flash, render

router = APIRouter(prefix="/copilot")

COPILOT_NOTICE = ("This interview will be followed by an AI assistant that listens, shows the recruiter a live transcript, suggests questions and "
                  "ticks the points of a good answer. It never decides: the recruiter asks, scores and decides. The conversation is recorded and kept for "
                  "6 months. You can ask for the interview to be held without the assistant.")


def _cand(db: Session, cand_id: int) -> Candidate:
    c = db.get(Candidate, cand_id)
    if c is None:
        raise HTTPException(404, "That candidate does not exist")
    return c


def _hi(db: Session, cand_id: int) -> HumanInterview | None:
    return db.scalars(select(HumanInterview).where(HumanInterview.candidate_id == cand_id).order_by(HumanInterview.id.desc())).first()


def recording_for(cand: Candidate) -> dict | None:
    return next((i for i in load_interviews() if i["cv_file"] == cand.cv_name), None)


@router.get("")
def copilot_home(request: Request, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    rows = []
    for c in db.scalars(select(Candidate).where(Candidate.stage.in_(["SHORTLISTED", "AI_INTERVIEW", "HUMAN_INTERVIEW", "DECISION"])).order_by(Candidate.id)):
        rows.append({"c": c, "rec": recording_for(c), "hi": _hi(db, c.id)})
    return render(request, "copilot_home.html", user, rows=rows)


@router.get("/{cand_id}")
def copilot_panel(request: Request, cand_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    cand = _cand(db, cand_id)
    return render(request, "copilot.html", user, cand=cand, rec=recording_for(cand), hi=_hi(db, cand_id), notice=COPILOT_NOTICE)


@router.post("/{cand_id}/to-human-interview")
def to_human_interview(request: Request, cand_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    cand = _cand(db, cand_id)
    session = db.query(InterviewSession).filter_by(candidate_id=cand.id).first()
    asked = bool(session and session.status == "PERSON_REQUESTED")
    try:
        move(db, cand, Stage.HUMAN_INTERVIEW, user.email, "interview with a person, as the candidate asked" if asked else "second-round interview with a recruiter",
             evidence={"asked_for_person": True} if asked else None)
        from app.agents.communications import draft_invitation
        draft_invitation(db, cand, kind="invitation")
    except MoveRefused as e:
        db.rollback()
        flash(request, f"Refused: {e}", "bad")
    else:
        db.commit()
        flash(request, "Moved to HUMAN_INTERVIEW. An invitation with a proposed slot is waiting in the outbox for your approval.")
    return RedirectResponse(f"/copilot/{cand_id}", status_code=303)


@router.post("/{cand_id}/ack")
def acknowledge(request: Request, cand_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """The recruiter confirms the candidate was told AI assists and did not ask for the interview without it (rule 5)."""
    cand = _cand(db, cand_id)
    rec = recording_for(cand)
    if rec is None:
        flash(request, "There is no recorded interview for this candidate.", "bad")
    else:
        hi = _hi(db, cand_id) or HumanInterview(candidate_id=cand_id, recording=rec["file"])
        hi.notice_ack, hi.status = True, "READY"
        db.add(hi)
        db.add(DecisionLog(actor=user.email, action="copilot notice confirmed", subject=f"candidate:{cand_id}", reason="candidate told an AI assistant follows the interview and agreed"))
        db.commit()
        flash(request, "Confirmed. The copilot can follow this interview.")
    return RedirectResponse(f"/copilot/{cand_id}", status_code=303)


@router.post("/{cand_id}/decline")
def decline(request: Request, cand_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """The candidate asked for the interview without the assistant: the copilot is not started."""
    hi = _hi(db, cand_id) or HumanInterview(candidate_id=cand_id)
    hi.status, hi.notice_ack = "NO_COPILOT", False
    db.add(hi)
    db.add(DecisionLog(actor=user.email, action="candidate declined the copilot", subject=f"candidate:{cand_id}", reason="interview held without the AI assistant"))
    db.commit()
    flash(request, "Noted: the interview will be held without the assistant.")
    return RedirectResponse(f"/copilot/{cand_id}", status_code=303)


@router.get("/{cand_id}/events")
def events(cand_id: int, speed: float = 8.0, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """Server-sent events: the copilot following the recorded interview (speed = replay seconds per real second; 0 = instant)."""
    cand = _cand(db, cand_id)
    rec = recording_for(cand)
    hi = _hi(db, cand_id)
    if rec is None or hi is None or not hi.notice_ack:
        raise HTTPException(403, "The candidate must be told about the AI assistant, and the recruiter must confirm it, before the copilot starts")
    req_id, hi_id = cand.requisition_id, hi.id

    def gen():
        with SessionLocal() as s:
            c, req = s.get(Candidate, cand_id), s.get(Requisition, req_id)
            agent = CopilotAgent(s, c, req)
            for turn in replay(rec, max(0.0, speed)):
                for e in agent.process_turn(turn["speaker"], turn["text"], turn["start"], turn["end"]):
                    yield f"event: copilot\ndata: {json.dumps(e.model_dump())}\n\n"
            draft = agent.draft_scorecard()
            row = s.get(HumanInterview, hi_id)
            row.events, row.draft_scorecard, row.status = [e.model_dump() for e in agent.events], draft, "DONE"
            s.add(DecisionLog(actor="system", action="copilot followed interview", subject=f"candidate:{cand_id}",
                              reason=f"{len(agent.warnings)} warning(s), {len(agent.conflicts)} CV check(s); draft scorecard saved for the recruiter"))
            s.commit()
            yield f"event: draft\ndata: {json.dumps(draft)}\n\n"
            yield "event: end\ndata: {}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/{cand_id}/scores")
async def recruiter_scores(request: Request, cand_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """The recruiter scores the interview (the copilot's draft is only a suggestion)."""
    hi = _hi(db, cand_id)
    if hi is None or hi.status != "DONE":
        flash(request, "Let the copilot follow the interview first.", "bad")
        return RedirectResponse(f"/copilot/{cand_id}", status_code=303)
    form = await request.form()
    scores = {k[len("score_"):]: int(v) for k, v in form.items() if k.startswith("score_") and str(v).isdigit() and 0 <= int(v) <= 3}
    hi.recruiter_scores = {"scores": scores, "by": user.email, "note": str(form.get("note", ""))}
    db.add(DecisionLog(actor=user.email, action="human interview scored", subject=f"candidate:{cand_id}", reason=str(form.get("note", ""))[:200],
                       evidence={"recruiter_scores": scores, "copilot_draft": hi.draft_scorecard}))
    db.commit()
    flash(request, "Your scores were saved. They replace the copilot's draft.")
    return RedirectResponse(f"/copilot/{cand_id}", status_code=303)


@router.get("/{cand_id}/audio")
def audio(cand_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    rec = recording_for(_cand(db, cand_id))
    p = Path(get_settings().kit_dir) / rec["file"] if rec else None
    if p is None or not p.exists():
        raise HTTPException(404, "No recording")
    return FileResponse(p, media_type="audio/wav")
