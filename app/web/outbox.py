"""The outbox: the approval queue for emails. Drafts wait here; a recruiter reads, edits, approves or rejects. Sent means a log row."""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.communications import SendRefused, approve_and_send, queue, reject_draft
from app.auth import RECRUITER, STAFF
from app.db import get_db
from app.models import User
from app.models_ext import EmailDraft, OutboxLog
from app.web.common import flash, render

router = APIRouter(prefix="/outbox")


@router.get("")
def outbox(request: Request, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    sent = db.scalars(select(OutboxLog).order_by(OutboxLog.id.desc()).limit(50)).all()
    return render(request, "outbox.html", user, drafts=queue(db), sent=sent)


@router.post("/{draft_id}/approve")
def approve(request: Request, draft_id: int, body: str = Form(""), user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    d = db.get(EmailDraft, draft_id)
    if d is None:
        raise HTTPException(404, "That draft does not exist")
    if body.strip() and body != d.body and d.status == "DRAFT":
        d.body = body.strip()  # the person edited the draft: what they approve is what is sent
    try:
        approve_and_send(db, draft_id, user.email)
    except SendRefused as e:
        db.rollback()
        flash(request, str(e), "bad")
    else:
        db.commit()
        flash(request, "Approved. The email was written to the outbox log (no real mail server exists).")
    return RedirectResponse("/outbox", status_code=303)


@router.post("/{draft_id}/reject")
def reject(request: Request, draft_id: int, reason: str = Form(""), user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    try:
        reject_draft(db, draft_id, user.email, reason)
    except SendRefused as e:
        db.rollback()
        flash(request, str(e), "bad")
    else:
        db.commit()
        flash(request, "Draft rejected. Nothing was sent.")
    return RedirectResponse("/outbox", status_code=303)
