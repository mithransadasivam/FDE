"""The AI first-round interview: the candidate's page (private link, no sign-in) and the recruiter's review (Day 2)."""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.interviewer import InterviewerAgent, get_or_create_session, request_person
from app.auth import RECRUITER, STAFF
from app.config import get_settings
from app.db import get_db
from app.interview.bank import diagram_path, load_questions
from app.interview.replay import load_recorded, run_recorded_interview
from app.models import Candidate, DecisionLog, Requisition, User
from app.models_ext import InterviewSession
from app.privacy import make_blind
from app.supervisor import MoveRefused, move
from app.schemas import Stage
from app.web.common import flash, render

router = APIRouter()
AUDIO_TYPES = {".wav", ".mp3", ".m4a", ".webm", ".ogg"}

NOTICE = ("You are about to talk to an AI interviewer. It will ask you up to 8 questions, some with a diagram. Your answers are recorded and "
          "turned into text, and the text is scored by AI against the skills for this role. Only what you say is scored, never your voice, "
          "accent or how you speak. A recruiter reviews every interview and makes every decision. Recordings are kept for 6 months and then "
          "deleted. If you would rather speak to a person, choose \"Ask for a person instead\": it will not affect how your application is treated.")


def _cand(db: Session, token: str) -> Candidate:
    c = db.scalar(select(Candidate).where(Candidate.access_token == token))
    if c is None:
        raise HTTPException(404, "We could not find that interview")
    return c


def _agent(db: Session, cand: Candidate) -> tuple[InterviewerAgent, Requisition]:
    req = db.get(Requisition, cand.requisition_id)
    return InterviewerAgent(db, get_or_create_session(db, cand)), req


# ---- the candidate's page -------------------------------------------------------------------------------------------------------
@router.get("/interview/{token}")
def interview_page(request: Request, token: str, db: Session = Depends(get_db)):
    cand = _cand(db, token)
    session = db.query(InterviewSession).filter_by(candidate_id=cand.id).first()
    invited = cand.stage == "AI_INTERVIEW"
    status = session.status if session else "NOT_STARTED"
    fixtures = [{"id": a["id"], "q": a["question_id"], "kind": a["kind"]} for a in load_recorded()] if get_settings().fake_models else []
    return render(request, "interview.html", None, cand=cand, invited=invited, status=status, notice=NOTICE, token=token,
                  title=db.get(Requisition, cand.requisition_id).title, fake=get_settings().fake_models, fixtures=fixtures,
                  acked=bool(session and session.notice_ack))


@router.post("/interview/{token}/notice")
def acknowledge_notice(token: str, db: Session = Depends(get_db)):
    cand = _cand(db, token)
    if cand.stage != "AI_INTERVIEW":
        raise HTTPException(403, "You have not been invited to an AI interview yet")
    s = get_or_create_session(db, cand)
    if not s.notice_ack:
        s.notice_ack = True
        db.add(DecisionLog(actor="candidate", action="AI notice acknowledged", subject=f"candidate:{cand.id}", reason="before the AI interview"))
    db.commit()
    return {"ok": True}


@router.post("/interview/{token}/start")
def start(token: str, db: Session = Depends(get_db)):
    cand = _cand(db, token)
    if cand.stage != "AI_INTERVIEW":
        raise HTTPException(403, "You have not been invited to an AI interview yet")
    agent, req = _agent(db, cand)
    try:
        return {"prompt": agent.start(req)}
    except PermissionError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/interview/{token}/state")
def state(token: str, db: Session = Depends(get_db)):
    cand = _cand(db, token)
    agent, _ = _agent(db, cand)
    return {"status": agent.session.status, "prompt": agent.next_prompt()}


@router.post("/interview/{token}/answer")
async def answer(token: str, audio: UploadFile | None = File(None), text: str = Form(""), fixture: str = Form(""), db: Session = Depends(get_db)):
    cand = _cand(db, token)
    agent, _ = _agent(db, cand)
    if agent.session.status != "IN_PROGRESS":
        raise HTTPException(409, "The interview is not in progress")
    try:
        if fixture and get_settings().fake_models:  # demo mode: play one of the recorded answers
            rec = next((a for a in load_recorded() if a["id"] == fixture), None)
            if rec is None:
                raise HTTPException(400, "Unknown recorded answer")
            path = Path(get_settings().kit_dir) / rec["file"]
            return agent.submit(audio_path=path, original_name=path.name, audio_ref=rec["file"])
        if audio is not None and audio.filename:
            suffix = Path(audio.filename).suffix.lower() or ".webm"
            if suffix not in AUDIO_TYPES:
                raise HTTPException(400, "That audio format is not accepted")
            data = await audio.read()
            if not data or len(data) > 25 * 1024 * 1024:
                raise HTTPException(400, "The recording is empty or too large")
            folder = get_settings().storage_dir / "interviews" / str(cand.id)
            folder.mkdir(parents=True, exist_ok=True)
            dest = folder / f"{uuid.uuid4().hex}{suffix}"
            dest.write_bytes(data)
            try:
                return agent.submit(audio_path=dest, original_name=audio.filename, audio_ref=str(dest.relative_to(get_settings().storage_dir)))
            except FileNotFoundError:
                if not text.strip():
                    raise HTTPException(422, "Fake mode cannot transcribe a new recording: type your answer in the box, or play a recorded answer") from None
        return agent.submit(text=text)
    except PermissionError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/interview/{token}/person")
def ask_for_person(token: str, db: Session = Depends(get_db)):
    cand = _cand(db, token)
    try:
        request_person(db, cand)
    except PermissionError as e:
        raise HTTPException(409, str(e)) from e
    return {"ok": True, "message": "Thank you. A recruiter will contact you to arrange an interview with a person."}


@router.get("/interview/{token}/diagram/{diagram_id}")
def diagram(token: str, diagram_id: str, db: Session = Depends(get_db)):
    cand = _cand(db, token)
    s = db.query(InterviewSession).filter_by(candidate_id=cand.id).first()
    allowed = {load_questions()[p["question_id"]].get("diagram") for p in (s.plan or [])} if s else set()
    p = diagram_path(diagram_id)
    if diagram_id not in allowed or p is None or not p.exists():
        raise HTTPException(404, "That diagram is not part of your interview")
    return FileResponse(p, media_type="image/png")


# ---- the recruiter's side -------------------------------------------------------------------------------------------------------
@router.get("/interviews")
def interviews(request: Request, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    rows = []
    for c in db.scalars(select(Candidate).where(Candidate.stage.in_(["SHORTLISTED", "AI_INTERVIEW", "HUMAN_INTERVIEW", "DECISION"])).order_by(Candidate.id)):
        s = db.query(InterviewSession).filter_by(candidate_id=c.id).first()
        rows.append({"c": c, "s": s, "blind": make_blind(c)})
    return render(request, "interviews.html", user, rows=rows)


@router.post("/interviews/{cand_id}/invite")
def invite(request: Request, cand_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    cand = db.get(Candidate, cand_id)
    if cand is None:
        raise HTTPException(404, "That candidate does not exist")
    try:
        move(db, cand, Stage.AI_INTERVIEW, user.email, "invited to the first-round AI interview")
        from app.agents.communications import draft_invitation
        draft_invitation(db, cand, kind="ai_interview")
    except MoveRefused as e:
        db.rollback()
        flash(request, f"Refused: {e}", "bad")
    else:
        db.commit()
        flash(request, f"Candidate #{cand.id} moved to AI_INTERVIEW. An invitation was drafted: approve it in the outbox before it is sent.")
    return RedirectResponse("/interviews", status_code=303)


@router.post("/interviews/{cand_id}/replay")
def replay(request: Request, cand_id: int, quality: str = Form("strong"), user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """Demo: run the whole interview from the recorded answers (only in fake mode)."""
    cand = db.get(Candidate, cand_id)
    if cand is None or cand.stage != "AI_INTERVIEW":
        flash(request, "The candidate must be invited to the AI interview first.", "bad")
    elif not get_settings().fake_models:
        flash(request, "Replaying recorded answers is only available in fake mode.", "bad")
    else:
        run_recorded_interview(db, cand, db.get(Requisition, cand.requisition_id), quality)
        flash(request, f"Interview for candidate #{cand.id} replayed from recorded answers. Review the scorecard below.")
    return RedirectResponse(f"/interviews/{cand_id}", status_code=303)


@router.get("/interviews/{cand_id}")
def interview_review(request: Request, cand_id: int, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    cand = db.get(Candidate, cand_id)
    if cand is None:
        raise HTTPException(404, "That candidate does not exist")
    s = db.query(InterviewSession).filter_by(candidate_id=cand_id).first()
    qs = load_questions()
    return render(request, "interview_review.html", user, cand=cand, s=s, qs=qs, blind=make_blind(cand))


@router.post("/interviews/{cand_id}/review")
def mark_reviewed(request: Request, cand_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    s = db.query(InterviewSession).filter_by(candidate_id=cand_id).first()
    if s is None or s.status != "DONE":
        flash(request, "There is no finished interview to review yet.", "bad")
    else:
        s.reviewed_by = user.email
        db.add(DecisionLog(actor=user.email, action="AI interview scorecard reviewed", subject=f"candidate:{cand_id}",
                           reason=f"average {s.scorecard.get('total')}/3; {len(s.scorecard.get('disagreements', []))} disagreement(s) read", evidence=s.scorecard))
        db.commit()
        flash(request, "Scorecard marked as reviewed by you.")
    return RedirectResponse(f"/interviews/{cand_id}", status_code=303)


@router.get("/media/interview/{cand_id}")
def media(cand_id: int, ref: str, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    """Interview audio, for the 'play the moment' links. Only staff, and only files under the kit or the interview storage folder."""
    roots = [Path(get_settings().kit_dir).resolve(), (get_settings().storage_dir / "interviews").resolve()]
    for root in roots:
        p = (root / ref).resolve() if not Path(ref).is_absolute() else Path(ref).resolve()
        if p.exists() and any(str(p).startswith(str(r)) for r in roots):
            return FileResponse(p)
    p = (get_settings().storage_dir / ref).resolve()
    if p.exists() and str(p).startswith(str((get_settings().storage_dir / "interviews").resolve())):
        return FileResponse(p)
    raise HTTPException(404, "That recording is not available")
