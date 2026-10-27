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
    from app.agents.wording import check_requisition

    req.job = draft.job.model_dump()
    req.rubric = draft.rubric.model_dump()
    req.wording_flags = [f.model_dump() for f in check_requisition(req.transcript, draft.job.as_text())]
    req.status = "GENERATED"
    db.add(DecisionLog(actor=user.email, action="draft generated", subject=f"requisition:{req.id}",
                       reason=f"{len(draft.rubric.items)} skills, weights add to {draft.rubric.total}, {len(req.wording_flags)} wording flag(s)"))
    db.commit()
    flash(request, "Job description and rubric generated. Please check them, then approve.")
    return RedirectResponse(f"/requisitions/{req.id}", status_code=303)


# ---- Prompt 9: edit, approve, publish ---------------------------------------------------------------
from pydantic import ValidationError  # noqa: E402

from app.agents.wording import check_requisition, check_wording  # noqa: E402
from app.schemas import JobDescription, Rubric  # noqa: E402


def _back(req_id: int) -> RedirectResponse:
    return RedirectResponse(f"/requisitions/{req_id}", status_code=303)


def _validation_message(e: ValidationError) -> str:
    return "; ".join(x["msg"].replace("Value error, ", "") for x in e.errors()[:3])


def _send_back_to_generated(db: Session, req: Requisition, user: User, what: str, reason: str) -> None:
    """Any edit needs a new approval, so the requisition goes back to GENERATED (and a live job is withdrawn)."""
    was = req.status
    req.status = "GENERATED"
    req.wording_flags = [f.model_dump() for f in check_requisition(req.transcript, JobDescription.model_validate(req.job).as_text())]
    db.add(DecisionLog(actor=user.email, action=what, subject=f"requisition:{req.id}",
                       reason=f"{reason} (was {was}; needs approval again)", evidence=req.rubric))


@router.post("/{req_id}/rubric")
async def edit_rubric(request: Request, req_id: int, user: User = Depends(HM), db: Session = Depends(get_db)):
    req = get_req(db, req_id)
    if req.status not in ("GENERATED", "APPROVED", "PUBLISHED") or not req.rubric:
        flash(request, "There is no rubric to edit yet.", "bad")
        return _back(req.id)
    form = await request.form()
    items = []
    try:
        for n, old in enumerate(req.rubric["items"]):
            if form.get(f"remove_{n}"):
                continue
            items.append({**old, "weight": int(form.get(f"weight_{n}", old["weight"])), "must_have": bool(form.get(f"must_{n}"))})
        rubric = Rubric(items=items, min_years=float(form.get("min_years", req.rubric["min_years"])))
    except ValueError as e:  # includes pydantic's ValidationError
        msg = _validation_message(e) if isinstance(e, ValidationError) else "Weights and years must be numbers."
        flash(request, f"The rubric was not saved: {msg}", "bad")
        return _back(req.id)
    before = req.rubric
    req.rubric = rubric.model_dump()
    _send_back_to_generated(db, req, user, "rubric edited", f"{len(rubric.items)} skills, weights add to {rubric.total}")
    db.commit()
    flash(request, "Rubric saved. It needs to be approved again.")
    return _back(req.id)


@router.post("/{req_id}/job")
async def edit_job(request: Request, req_id: int, user: User = Depends(HM), db: Session = Depends(get_db)):
    req = get_req(db, req_id)
    if req.status not in ("GENERATED", "APPROVED", "PUBLISHED") or not req.job:
        flash(request, "There is no job description to edit yet.", "bad")
        return _back(req.id)
    form = await request.form()

    def lines(key: str) -> list[str]:
        return [ln.strip() for ln in str(form.get(key, "")).splitlines() if ln.strip()]

    try:
        job = JobDescription(title=str(form.get("title", "")).strip(), summary=str(form.get("summary", "")).strip(),
                             responsibilities=lines("responsibilities"), requirements=lines("requirements"),
                             nice_to_have=lines("nice_to_have"))
    except ValidationError as e:
        flash(request, f"The job description was not saved: {_validation_message(e)}", "bad")
        return _back(req.id)
    req.job = job.model_dump()
    _send_back_to_generated(db, req, user, "job text edited", "job description changed")
    db.commit()
    flash(request, "Job description saved. Check the wording flags, then approve.")
    return _back(req.id)


@router.post("/{req_id}/approve")
def approve(request: Request, req_id: int, comment: str = Form(""), user: User = Depends(HM), db: Session = Depends(get_db)):
    req = get_req(db, req_id)
    if req.status != "GENERATED":  # checked here on the server, not only by hiding the button
        flash(request, "The rubric can only be approved when it is generated and has not been approved yet.", "bad")
        return _back(req.id)
    job = JobDescription.model_validate(req.job)
    flagged = check_wording(job.as_text(), "job text")
    if flagged:
        flash(request, "Not approved: the job text still has biased wording ("
                       + ", ".join(f'"{f.phrase}"' for f in flagged) + "). Change it first.", "bad")
        return _back(req.id)
    rubric = Rubric.model_validate(req.rubric)  # one more check that the weights still add to 100
    req.status = "APPROVED"
    db.add(DecisionLog(actor=user.email, action="rubric approved", subject=f"requisition:{req.id}",
                       reason=comment.strip(), evidence={"rubric": rubric.model_dump(), "job": req.job,
                                                         "wording_flags_in_voice_note": req.wording_flags}))
    db.commit()
    flash(request, "Rubric approved. You can now publish the job.")
    return _back(req.id)


@router.post("/{req_id}/publish")
def publish(request: Request, req_id: int, user: User = Depends(HM), db: Session = Depends(get_db)):
    req = get_req(db, req_id)
    if req.status != "APPROVED":
        flash(request, "A job can only be published after the rubric is approved.", "bad")
        return _back(req.id)
    req.status = "PUBLISHED"
    db.add(DecisionLog(actor=user.email, action="job published", subject=f"requisition:{req.id}", reason=req.title))
    db.commit()
    flash(request, f"Job published. Candidates can apply at /jobs/{req.id}.")
    return _back(req.id)
