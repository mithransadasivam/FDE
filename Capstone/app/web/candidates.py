"""Candidates, the review queue and identity hiding (Prompt 12). The pipeline board is added in Prompt 13."""
from pathlib import Path

from types import SimpleNamespace

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import RECRUITER, STAFF
from app.db import get_db
from app.duplicates import duplicate_map
from app.models import Candidate, DecisionLog, Requisition, ReviewItem, User
from app.models_ext import EvidenceCheck, Flag, ItemScoreRow
from app.privacy import identity_leaks, make_blind
from app.schemas import CandidateProfile, Stage
from app.supervisor import ALLOWED, MoveRefused, move
from app.services import CORE_FIELDS, OPTIONAL_FIELDS, correct_fields, value_text
from app.credentials import credential_checks
from app.privacy import redact_identity
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
def candidates(request: Request, blind: int | None = None, job: int | None = None, stage: str = "", skill: str = "", min_years: float | None = None,
               min_total: float | None = None, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    """The candidate list, with filters: stage, a skill (blind text), minimum years and minimum CV score. Filters use blind facts only."""
    is_blind = effective_blind(user, blind)
    query = select(Candidate).order_by(Candidate.id)
    if job:
        query = query.where(Candidate.requisition_id == job)
    if stage:
        query = query.where(Candidate.stage == stage)
    totals: dict[int, float] = {}
    for cid, total in db.execute(select(ItemScoreRow.candidate_id, func.sum(ItemScoreRow.weight * ItemScoreRow.score)).group_by(ItemScoreRow.candidate_id)).all():
        totals[cid] = round(float(total) / 3, 1)
    rows = []
    dups = duplicate_map(db)
    for c in db.scalars(query):
        b = make_blind(c)
        if skill and not any(skill.lower() in sk.lower() for sk in b.skills):
            continue
        if min_years is not None and (b.years_experience or 0) < min_years:
            continue
        if min_total is not None and totals.get(c.id, -1) < min_total:
            continue
        if is_blind:
            rows.append({"c": c, "name": f"Candidate #{c.id}", "title": b.current_title, "years": b.years_experience, "skills": b.skills, "total": totals.get(c.id)})
        else:
            p = CandidateProfile.model_validate(c.profile or {})
            rows.append({"c": c, "name": p.name.value or "(not read)", "title": p.current_title.value,
                         "years": p.years_experience.value, "skills": p.skills.value or [], "total": totals.get(c.id)})
    return render(request, "candidates.html", user, rows=rows, is_blind=is_blind, job=job, dups=dups, stage=stage, skill=skill, min_years=min_years,
                  min_total=min_total, stages=[s.value for s in Stage],
                  filtered=bool(stage or skill or min_years is not None or min_total is not None))


@router.get("/candidates/{cand_id}")
def candidate(request: Request, cand_id: int, blind: int | None = None, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    cand = get_candidate(db, cand_id)
    is_blind = effective_blind(user, blind)
    profile = CandidateProfile.model_validate(cand.profile or {})
    fields = [(f, FIELD_LABELS[f], getattr(profile, f)) for f in CORE_FIELDS + OPTIONAL_FIELDS]
    pending = db.scalars(select(ReviewItem).where(ReviewItem.candidate_id == cand.id, ReviewItem.resolved.is_(False))).all()
    scores = list(db.scalars(select(ItemScoreRow).where(ItemScoreRow.candidate_id == cand.id).order_by(ItemScoreRow.id)))
    flags = [SimpleNamespace(kind=f.kind, detail=redact_identity(cand, f.detail)) for f in db.scalars(select(Flag).where(Flag.candidate_id == cand.id))]  # flags can quote text next to the name
    from app.interview.scorecard import build_card
    from app.models_ext import HumanInterviewScore, InterviewSession
    iv = db.query(InterviewSession).filter_by(candidate_id=cand.id).first()
    ai_card = build_card(db, iv) if iv and iv.status == "DONE" and iv.scorecard else None
    human_scores = list(db.scalars(select(HumanInterviewScore).where(HumanInterviewScore.candidate_id == cand.id).order_by(HumanInterviewScore.id)))
    return render(request, "candidate.html", user, cand=cand, blind_record=make_blind(cand), is_blind=is_blind, fields=fields,
                  checks=list(db.scalars(select(EvidenceCheck).where(EvidenceCheck.candidate_id == cand.id))), ai_card=ai_card, human_scores=human_scores, pending=pending, threshold=0.8, twins=duplicate_map(db).get(cand.id, []), scores=scores, flags=flags, credentials=credential_checks(cand.profile),
                  score_total=round(sum(r.weight * r.score for r in scores) / 3, 1) if scores else None)


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
        try:
            move(db, cand, Stage.EXTRACTED, user.email, "review complete: every unsure field was checked by a person")
        except MoveRefused as e:
            flash(request, str(e), "bad")
            return RedirectResponse("/review", status_code=303)
        cand.error = None
        db.commit()
        flash(request, f"Candidate #{cand.id} confirmed and moved to EXTRACTED.")
    return RedirectResponse("/review", status_code=303)


# ---- pipeline board (Prompt 13) -------------------------------------------------------------------------------------
@router.get("/pipeline")
def pipeline(request: Request, blind: int | None = None, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    is_blind = effective_blind(user, blind)
    columns = {s: [] for s in Stage}
    everyone = []
    dups = duplicate_map(db)
    from app.models_ext import InterviewSession
    asked = {i.candidate_id for i in db.scalars(select(InterviewSession).where(InterviewSession.status == "PERSON_REQUESTED"))}
    for c in db.scalars(select(Candidate).order_by(Candidate.id)):
        p = CandidateProfile.model_validate(c.profile or {})
        label = f"Candidate #{c.id}" if is_blind else (p.name.value or f"Candidate #{c.id}")
        chip = {"id": c.id, "label": label, "title": make_blind(c).current_title if is_blind else p.current_title.value,
                "format": c.cv_format, "dup": dups.get(c.id, []), "person": c.id in asked}
        columns[Stage(c.stage)].append(chip)
        everyone.append(chip)
    allowed = {s.value: [(t.value, who) for t, who in moves.items()] for s, moves in ALLOWED.items()}
    return render(request, "pipeline.html", user, columns=columns, everyone=everyone, is_blind=is_blind, allowed=allowed,
                  stages=[s.value for s in Stage])


@router.post("/pipeline/move")
def pipeline_move(request: Request, candidate_id: int = Form(...), to: str = Form(...), reason: str = Form(""),
                  user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """A person moves a candidate. The supervisor refuses anything the table of allowed moves does not permit."""
    cand = get_candidate(db, candidate_id)
    try:
        frm = cand.stage
        move(db, cand, to, user.email, reason)
    except MoveRefused as e:
        db.rollback()
        flash(request, f"Refused: {e}", "bad")
    else:
        db.commit()
        flash(request, f"Candidate #{cand.id} moved from {frm} to {to}.")
    return RedirectResponse("/pipeline", status_code=303)
