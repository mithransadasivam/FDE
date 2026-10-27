"""The candidates' side: no sign-in. Open jobs, the AI notice, consent, CV upload and a private link (Prompt 10)."""
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Candidate, DecisionLog, Requisition
from app.services import process_candidate
from app.web.common import render, save_upload

router = APIRouter()

# extension -> CV format. The starter kit's photographed scans are .jpg and its profile screenshots are .png.
FORMATS = {".pdf": "pdf", ".docx": "docx", ".png": "screenshot", ".jpg": "scan", ".jpeg": "scan"}
MAX_CV_BYTES = 5 * 1024 * 1024

STAGE_TEXT = {
    "APPLIED": "We have received your application and are reading your CV.",
    "EXTRACTED": "Your CV has been read. A recruiter will look at your application.",
    "REVIEW": "Your CV has been read. A recruiter is checking a few details.",
    "SCREENED": "Your application has been compared with the skills for the role. A recruiter will decide the next step.",
    "SHORTLISTED": "A recruiter has put you on the shortlist.",
    "AI_INTERVIEW": "You may be invited to a first interview. You can ask for a person instead.",
    "HUMAN_INTERVIEW": "You are at the interview stage with a recruiter.",
    "DECISION": "A recruiter is making a decision.",
    "WITHDRAWN": "This application is no longer active.",
}


def _published(db: Session, job_id: int) -> Requisition:
    req = db.get(Requisition, job_id)
    if req is None or req.status != "PUBLISHED":
        raise HTTPException(404, "That job is not open for applications")
    return req


def _by_token(db: Session, token: str) -> Candidate:
    cand = db.scalar(select(Candidate).where(Candidate.access_token == token))
    if cand is None:
        raise HTTPException(404, "We could not find that application")
    return cand


@router.get("/jobs")
def jobs(request: Request, db: Session = Depends(get_db)):
    reqs = db.scalars(select(Requisition).where(Requisition.status == "PUBLISHED").order_by(Requisition.id)).all()
    return render(request, "jobs.html", None, reqs=reqs)


@router.get("/jobs/{job_id}")
def job(request: Request, job_id: int, db: Session = Depends(get_db)):
    req = _published(db, job_id)
    return render(request, "job.html", None, req=req, retention_days=get_settings().retention_days)


@router.post("/jobs/{job_id}/apply")
async def apply(request: Request, job_id: int, background: BackgroundTasks, consent: str = Form(""),
                cv: UploadFile = File(...), db: Session = Depends(get_db)):
    req = _published(db, job_id)
    days = get_settings().retention_days
    # Consent is checked here on the server: removing the tick box in the browser must not get round it.
    if consent != "yes":
        return render(request, "job.html", None, status_code=400, req=req, retention_days=days,
                      error="Please read the notice and tick the box to apply.")
    try:
        path = await save_upload(cv, "cvs", set(FORMATS), MAX_CV_BYTES)
    except HTTPException as e:
        return render(request, "job.html", None, status_code=e.status_code, req=req, retention_days=days, error=e.detail)
    cand = Candidate(requisition_id=req.id, cv_path=str(path), cv_name=cv.filename or path.name,
                     cv_format=FORMATS[path.suffix.lower()], consent_ai=True,
                     access_token=secrets.token_urlsafe(24), stage="APPLIED")
    db.add(cand)
    db.flush()
    db.add(DecisionLog(actor="candidate", action="applied, consent to AI given", subject=f"candidate:{cand.id}",
                       reason=f"for requisition {req.id}; CV format {cand.cv_format}"))
    db.commit()
    background.add_task(process_candidate, cand.id)  # reading the CV comes next (Prompt 11)
    return RedirectResponse(f"/applied/{cand.access_token}", status_code=303)


@router.get("/applied/{token}")
def applied(request: Request, token: str, db: Session = Depends(get_db)):
    return render(request, "applied.html", None, cand=_by_token(db, token))


@router.post("/me/{token}/explain")
def explain(request: Request, token: str, db: Session = Depends(get_db)):
    """The candidate asks why they were not shortlisted. A plain explanation is drafted from the evidence for a recruiter to review (BR-19)."""
    from app.decisions import explain_not_shortlisted
    from app.supervisor import MoveRefused
    cand = _by_token(db, token)
    try:
        explain_not_shortlisted(db, cand)
    except MoveRefused as e:
        return RedirectResponse(f"/me/{token}?explain=refused", status_code=303)
    db.commit()
    return RedirectResponse(f"/me/{token}?explain=asked", status_code=303)


@router.post("/me/{token}/message")
def send_message(request: Request, token: str, message: str = Form(""), db: Session = Depends(get_db)):
    """A candidate writes to us. The text is data: it is logged, scanned for instructions and answered by a draft a recruiter must approve."""
    from app.agents.communications import handle_candidate_message
    cand = _by_token(db, token)
    handle_candidate_message(db, cand, message)
    db.commit()
    return RedirectResponse(f"/me/{token}?sent=1", status_code=303)


@router.get("/me/{token}")
def me(request: Request, token: str, db: Session = Depends(get_db)):
    cand = _by_token(db, token)
    return render(request, "me.html", None, cand=cand, status_text=STAGE_TEXT.get(cand.stage, ""),
                  retention_days=get_settings().retention_days, sent=request.query_params.get("sent") == "1",
                  explain=request.query_params.get("explain"), can_explain=cand.stage in ("SCREENED", "WITHDRAWN", "DECISION"))
