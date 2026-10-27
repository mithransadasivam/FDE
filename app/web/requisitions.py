"""Requisitions: upload a voice note (Prompt 5), transcribe it (6); generate, edit, approve, publish come in 7-9."""
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import HM, STAFF
from app.db import get_db
from app.models import Candidate, DecisionLog, Requisition, User
from app.services import transcribe_requisition
from app.web.common import flash, render, save_upload

router = APIRouter(prefix="/requisitions")

AUDIO_TYPES = {".wav", ".mp3", ".m4a", ".webm", ".ogg"}
MAX_AUDIO = 25 * 1024 * 1024
AUDIO_MEDIA = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".webm": "audio/webm", ".ogg": "audio/ogg"}


def get_req(db: Session, req_id: int) -> Requisition:
    req = db.get(Requisition, req_id)
    if req is None:
        raise HTTPException(404, "That requisition does not exist")
    return req


@router.get("")
def list_requisitions(request: Request, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    reqs = db.scalars(select(Requisition).order_by(Requisition.id)).all()
    counts = dict(db.execute(select(Candidate.requisition_id, func.count()).group_by(Candidate.requisition_id)).all())
    return render(request, "requisitions.html", user, reqs=reqs, counts=counts)


@router.get("/new")
def new_form(request: Request, user: User = Depends(HM)):
    return render(request, "requisition_new.html", user)


@router.post("")
async def create(request: Request, background: BackgroundTasks, title: str = Form(""), audio: UploadFile = File(...),
                 user: User = Depends(HM), db: Session = Depends(get_db)):
    title = title.strip()
    if not title:
        return render(request, "requisition_new.html", user, status_code=400, error="Please give the role a working title.")
    try:
        path = await save_upload(audio, "audio", AUDIO_TYPES, MAX_AUDIO)
    except HTTPException as e:
        return render(request, "requisition_new.html", user, status_code=e.status_code, error=e.detail, title=title)
    req = Requisition(title=title, created_by=user.email, audio_path=str(path), audio_name=audio.filename or path.name, status="DRAFT")
    db.add(req)
    db.flush()
    db.add(DecisionLog(actor=user.email, action="requisition created", subject=f"requisition:{req.id}", reason=title))
    db.commit()
    background.add_task(transcribe_requisition, req.id)  # the page replies at once; the transcript arrives shortly
    flash(request, "Voice note saved. Transcribing now; refresh in a moment.")
    return RedirectResponse(f"/requisitions/{req.id}", status_code=303)


@router.get("/{req_id}")
def detail(request: Request, req_id: int, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    req = get_req(db, req_id)
    total = sum(i["weight"] for i in req.rubric["items"]) if req.rubric else 0
    return render(request, "requisition.html", user, req=req, rubric_total=total)


@router.get("/{req_id}/audio")
def audio(req_id: int, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    """Only signed-in staff can listen to a voice note (recordings are personal data)."""
    req = get_req(db, req_id)
    from pathlib import Path

    p = Path(req.audio_path)
    if not p.exists():
        raise HTTPException(404, "The recording is no longer stored")
    return FileResponse(p, media_type=AUDIO_MEDIA.get(p.suffix.lower(), "application/octet-stream"))


@router.post("/{req_id}/generate")
def generate(request: Request, req_id: int, user: User = Depends(HM), db: Session = Depends(get_db)):
    from app.agents.requisition import generate_job
    from app.ai.llm import ModelError

    req = get_req(db, req_id)
    if req.status not in ("TRANSCRIBED", "GENERATED") or not req.transcript:
        flash(request, "The job description can only be generated once the voice note is transcribed (and before approval).", "bad")
        return RedirectResponse(f"/requisitions/{req.id}", status_code=303)
    try:
        draft = generate_job(req.transcript)
    except ModelError as e:
        flash(request, f"Could not generate the job description: {e}", "bad")
        return RedirectResponse(f"/requisitions/{req.id}", status_code=303)
    req.job = draft.job.model_dump()
    req.rubric = draft.rubric.model_dump()
    req.status = "GENERATED"
    db.add(DecisionLog(actor=user.email, action="draft generated", subject=f"requisition:{req.id}",
                       reason=f"{len(draft.rubric.items)} skills, weights add to {draft.rubric.total}"))
    db.commit()
    flash(request, "Job description and rubric generated. Please check them, then approve.")
    return RedirectResponse(f"/requisitions/{req.id}", status_code=303)
