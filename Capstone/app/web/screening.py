"""Screening and the shortlist (Day 2). Recruiters run scoring and approve the shortlist; hiring managers can look (blind)."""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RECRUITER, STAFF
from app.db import get_db
from app.models import Candidate, Requisition, User
from app.models_ext import ItemScoreRow, ShortlistEntry
from app.shortlist import approve_shortlist, scores_for, suggest_shortlist, weighted_total
from app.supervisor import MoveRefused
from app.web.common import flash, render
from app.agents.screening import screen_requisition

router = APIRouter(prefix="/screening")


@router.get("")
def screening_home(request: Request, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    reqs = db.scalars(select(Requisition).where(Requisition.status.in_(["APPROVED", "PUBLISHED"])).order_by(Requisition.id)).all()
    stats = {}
    for r in reqs:
        total = db.scalars(select(Candidate).where(Candidate.requisition_id == r.id)).all()
        stats[r.id] = {"candidates": len(total), "screened": sum(1 for c in total if c.stage not in ("APPLIED", "EXTRACTED", "REVIEW", "WITHDRAWN")),
                       "shortlisted": sum(1 for c in total if c.stage in ("SHORTLISTED", "AI_INTERVIEW", "HUMAN_INTERVIEW", "DECISION"))}
    return render(request, "screening_home.html", user, reqs=reqs, stats=stats)


@router.get("/{req_id}")
def screening_job(request: Request, req_id: int, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    req = db.get(Requisition, req_id)
    if req is None:
        raise HTTPException(404, "That requisition does not exist")
    entries = db.scalars(select(ShortlistEntry).where(ShortlistEntry.requisition_id == req_id).order_by(ShortlistEntry.rank)).all()
    cands = {c.id: c for c in db.scalars(select(Candidate).where(Candidate.requisition_id == req_id))}
    rows = []
    for e in entries:
        sc = scores_for(db, req_id, e.candidate_id)
        rows.append({"e": e, "cand": cands[e.candidate_id], "scores": sc})
    unscored = [c for c in cands.values() if c.stage in ("EXTRACTED", "REVIEW")]
    from app.models_ext import Flag
    flagged = {f.candidate_id for f in db.scalars(select(Flag).where(Flag.kind.in_(["hidden text in CV", "instructions in CV ignored"])))}
    from app.models_ext import EvidenceCheck
    checks = {c.candidate_id: c for c in db.scalars(select(EvidenceCheck).where(EvidenceCheck.subject == "screening"))}
    return render(request, "screening_job.html", user, req=req, rows=rows, unscored=unscored, flagged=flagged, checks=checks,
                  skills=[i["skill"] for i in (req.rubric or {}).get("items", [])])


@router.post("/{req_id}/run")
def run_screening(request: Request, req_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    try:
        out = screen_requisition(db, req_id, user.email)
    except ValueError as e:
        flash(request, str(e), "bad")
        return RedirectResponse(f"/screening/{req_id}", status_code=303)
    from app.agents.compliance import review
    review(db, req_id)  # the compliance reviewer checks every quote BEFORE the recruiter sees the shortlist
    suggest_shortlist(db, req_id)
    from app.agents.checker import run_checks
    run_checks(db, req_id)  # the evidence checker reports before the recruiter sees the shortlist
    flash(request, f"Scored {out['scored']} candidate(s); {out['waiting_in_review']} still waiting in the review queue. A shortlist is suggested below: a recruiter must approve it.")
    return RedirectResponse(f"/screening/{req_id}", status_code=303)


@router.post("/{req_id}/approve")
async def approve(request: Request, req_id: int, reason: str = Form(""), user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    form = await request.form()
    ids = [int(v) for k, v in form.multi_items() if k == "candidate_id"]
    try:
        moved = approve_shortlist(db, req_id, ids, user.email, reason)
    except MoveRefused as e:
        db.rollback()
        flash(request, f"Not approved: {e}", "bad")
    else:
        flash(request, f"Shortlist approved: {len(moved)} candidate(s) moved to SHORTLISTED. Your reason is in the decision log.")
    return RedirectResponse(f"/screening/{req_id}", status_code=303)


@router.post("/checks/{check_id}/ack")
def acknowledge_check(request: Request, check_id: int, back: str = Form("/screening"), user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """A recruiter says "I have looked at these" about the evidence checker's problems. Only then can the candidate be shortlisted or decided on."""
    from app.agents.checker import acknowledge

    try:
        acknowledge(db, check_id, user.email)
    except (LookupError, PermissionError) as e:
        db.rollback()
        flash(request, str(e), "bad")
    else:
        db.commit()
        flash(request, "Noted: you have looked at the evidence checker's problems. They stay on the record.")
    return RedirectResponse(back if back.startswith("/") and not back.startswith("//") else "/screening", status_code=303)


@router.post("/{req_id}/draft-not-shortlisted")
def draft_not_shortlisted(request: Request, req_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """Drafts a kind "not shortlisted" email for every screened candidate who was not shortlisted. Each draft waits in the outbox: nothing is sent."""
    from app.agents.communications import CommsAgent
    from app.models_ext import EmailDraft

    n = 0
    for cand in db.scalars(select(Candidate).where(Candidate.requisition_id == req_id, Candidate.stage == "SCREENED").order_by(Candidate.id)):
        if db.scalars(select(EmailDraft).where(EmailDraft.candidate_id == cand.id, EmailDraft.kind == "not_shortlisted")).first():
            continue
        CommsAgent(db, cand.id).call("draft_email", candidate_id=cand.id, kind="not_shortlisted")
        n += 1
    db.commit()
    flash(request, f"{n} \"not shortlisted\" draft(s) are waiting in the outbox. Nothing is sent until you approve each one.")
    return RedirectResponse(f"/screening/{req_id}", status_code=303)
