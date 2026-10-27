"""Candidates, the review queue and identity hiding (Prompt 12). The pipeline board is added in Prompt 13."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import RECRUITER, STAFF
from app.db import get_db
from app.models import Candidate, DecisionLog, Requisition, ReviewItem, User
from app.privacy import identity_leaks, make_blind
from app.schemas import CandidateProfile
from app.services import CORE_FIELDS, OPTIONAL_FIELDS, correct_fields, value_text
from app.web.common import flash, render, templates

router = APIRouter()
templates.env.filters["vt"] = value_text

FIELD_LABELS = {"name": "Name", "email": "Email", "phone": "Phone", "address": "Address", "date_of_birth": "Date of birth",
                "current_title": "Current title", "jobs": "Jobs", "years_experience": "Years of experience (from dates)",
                "skills": "Skills", "certifications": "Certifications", "education": "Education"}
IDENTITY_FIELDS = {"name", "email", "phone", "address", "date_of_birth"}


def effective_blind(user: User, blind: int | None) -> bool:
    """Least privilege, enforced here in the route: only recruiters may see identity, and only when they ask to.
    A hiring manager always gets the blind view, whatever the URL says."""
    return True if user.role != "recruiter" else bool(blind)


def get_candidate(db: Session, cand_id: int) -> Candidate:
    cand = db.get(Candidate, cand_id)
    if cand is None:
        raise HTTPException(404, "That candidate does not exist")
    return cand


@router.get("/candidates")
def candidates(request: Request, blind: int | None = None, job: int | None = None, user: User = Depends(STAFF),
               db: Session = Depends(get_db)):
    is_blind = effective_blind(user, blind)
    query = select(Candidate).order_by(Candidate.id)
    if job:
        query = query.where(Candidate.requisition_id == job)
    rows = []
    for c in db.scalars(query):
        if is_blind:
            b = make_blind(c)
            rows.append({"c": c, "name": f"Candidate #{c.id}", "title": b.current_title, "years": b.years_experience,
                         "skills": b.skills})
        else:
            p = CandidateProfile.model_validate(c.profile or {})
            rows.append({"c": c, "name": p.name.value or "(not read)", "title": p.current_title.value,
                         "years": p.years_experience.value, "skills": p.skills.value or []})
    return render(request, "candidates.html", user, rows=rows, is_blind=is_blind, job=job)


@router.get("/candidates/{cand_id}")
def candidate(request: Request, cand_id: int, blind: int | None = None, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    cand = get_candidate(db, cand_id)
    is_blind = effective_blind(user, blind)
    profile = CandidateProfile.model_validate(cand.profile or {})
    fields = [(f, FIELD_LABELS[f], getattr(profile, f)) for f in CORE_FIELDS + OPTIONAL_FIELDS]
    pending = db.scalars(select(ReviewItem).where(ReviewItem.candidate_id == cand.id, ReviewItem.resolved.is_(False))).all()
    return render(request, "candidate.html", user, cand=cand, blind_record=make_blind(cand), is_blind=is_blind, fields=fields,
                  pending=pending, threshold=0.8)


@router.get("/candidates/{cand_id}/cv")
def candidate_cv(cand_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """The original CV (it shows identity), so recruiters only."""
    cand = get_candidate(db, cand_id)
    path = Path(cand.cv_path)
    if not path.exists():
        raise HTTPException(404, "The CV is no longer stored")
    return FileResponse(path, filename=cand.cv_name)


# ---- review queue (recruiters only: it shows identity fields) -------------------------------------------------------
@router.get("/review")
def review(request: Request, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    waiting = db.scalars(select(Candidate).where(Candidate.stage == "REVIEW").order_by(Candidate.id)).all()
    items = {}
    for it in db.scalars(select(ReviewItem).where(ReviewItem.resolved.is_(False)).order_by(ReviewItem.id)):
        items.setdefault(it.candidate_id, []).append(it)
    total = sum(len(v) for v in items.values())
    return render(request, "review.html", user, waiting=waiting, items=items, total=total, labels=FIELD_LABELS)


@router.post("/review/{cand_id}/save")
async def review_save(request: Request, cand_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    cand = get_candidate(db, cand_id)
    form = await request.form()
    submitted = {k[len("value_"):]: str(v) for k, v in form.items() if k.startswith("value_") and k[len("value_"):] in FIELD_LABELS}
    if not submitted:
        flash(request, "Nothing to save.", "bad")
        return RedirectResponse("/review", status_code=303)
    try:
        changed = correct_fields(db, cand, submitted, user.email)
    except ValueError:
        db.rollback()
        flash(request, "Years of experience must be a number.", "bad")
        return RedirectResponse("/review", status_code=303)
    db.commit()
    flash(request, f"Saved candidate #{cand.id}: {len(submitted)} field(s) checked" + (f", changed: {', '.join(changed)}." if changed else "."))
    return RedirectResponse("/review", status_code=303)


@router.post("/review/{cand_id}/confirm")
def review_confirm(request: Request, cand_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    cand = get_candidate(db, cand_id)
    left = db.scalars(select(ReviewItem).where(ReviewItem.candidate_id == cand.id, ReviewItem.resolved.is_(False))).all()
    if cand.stage != "REVIEW":
        flash(request, f"Candidate #{cand.id} is not waiting for review.", "bad")
    elif left:
        flash(request, f"Candidate #{cand.id} still has {len(left)} field(s) to check.", "bad")
    else:
        cand.stage = "EXTRACTED"
        cand.error = None
        db.add(DecisionLog(actor=user.email, action="move REVIEW -> EXTRACTED", subject=f"candidate:{cand.id}",
                           reason="review complete: every unsure field was checked by a person"))
        db.commit()
        flash(request, f"Candidate #{cand.id} confirmed and moved to EXTRACTED.")
    return RedirectResponse("/review", status_code=303)
