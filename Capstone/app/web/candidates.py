"""Candidates, the review queue and identity hiding (Prompt 12). The pipeline board is added in Prompt 13."""
import re
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
               min_total: float | None = None, q: str = "", sort: str = "id", dir: str = "asc", user: User = Depends(STAFF), db: Session = Depends(get_db)):
    """The candidate list: filters (stage, a skill, minimum years and score), a search box, sorting, and a tick-box to compare. Filters use blind facts only."""
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
    needle = q.strip().lower().lstrip("#")
    for c in db.scalars(query):
        b = make_blind(c)
        if skill and not any(skill.lower() in sk.lower() for sk in b.skills):
            continue
        if min_years is not None and (b.years_experience or 0) < min_years:
            continue
        if min_total is not None and totals.get(c.id, -1) < min_total:
            continue
        if is_blind:
            row = {"c": c, "name": f"Candidate #{c.id}", "title": b.current_title, "years": b.years_experience, "skills": b.skills, "total": totals.get(c.id), "initial": "#"}
        else:
            p = CandidateProfile.model_validate(c.profile or {})
            row = {"c": c, "name": p.name.value or "(not read)", "title": p.current_title.value, "years": p.years_experience.value, "skills": p.skills.value or [], "total": totals.get(c.id)}
            row["initial"] = (row["name"] or "?")[:1]
        if needle and not (needle in row["name"].lower() or needle in (row["title"] or "").lower() or any(needle in x.lower() for x in row["skills"]) or (needle.isdigit() and c.id == int(needle))):
            continue
        rows.append(row)
    keys = {"id": lambda r: r["c"].id, "name": lambda r: r["name"].lower(), "years": lambda r: r["years"] or 0, "score": lambda r: r["total"] if r["total"] is not None else -1, "stage": lambda r: r["c"].stage}
    sort = sort if sort in keys else "id"
    rows.sort(key=keys[sort], reverse=(dir == "desc"))
    req_id = job or (rows[0]["c"].requisition_id if rows else 1)
    return render(request, "candidates.html", user, rows=rows, is_blind=is_blind, job=job, dups=dups, stage=stage, skill=skill, min_years=min_years,
                  min_total=min_total, stages=[s.value for s in Stage], q=q, sort=sort, dir=dir, req_id=req_id,
                  filtered=bool(stage or skill or q.strip() or min_years is not None or min_total is not None))


MENTION = re.compile(r"@([A-Za-z0-9_.-]{2,40})")


def notes_context(db: Session, cand: Candidate, hide_identity: bool) -> dict:
    """The notes on a candidate, newest first. Identity is hidden in the text whenever the page is blind."""
    from app.models_ext import CandidateNote

    rows = list(db.scalars(select(CandidateNote).where(CandidateNote.candidate_id == cand.id).order_by(CandidateNote.id.desc())))
    notes = [SimpleNamespace(id=n.id, author=n.author, role=n.author_role, at=n.created_at, mentions=n.mentions or [],
                             body=redact_identity(cand, n.body) if hide_identity else n.body) for n in rows]
    return {"notes": notes}


@router.post("/candidates/{cand_id}/notes")
def add_note(request: Request, cand_id: int, body: str = Form(""), blind: int = Form(0), user: User = Depends(STAFF), db: Session = Depends(get_db)):
    """Leave a note for the team. @name mentions a colleague (the part of their e-mail before the @). Logged, so the trail shows who said what."""
    from app.models_ext import CandidateNote

    cand = get_candidate(db, cand_id)
    text = (body or "").strip()
    back = f"/candidates/{cand_id}{'?blind=1' if blind else ''}#notes"
    if not text:
        flash(request, "Write something first: an empty note was not saved.", "bad")
        return RedirectResponse(back, status_code=303)
    people = {u.email.split("@")[0].lower(): u.email for u in db.scalars(select(User).where(User.is_active.is_(True)))}
    mentions = sorted({people[m.lower()] for m in MENTION.findall(text) if m.lower() in people})
    db.add(CandidateNote(candidate_id=cand.id, author=user.email, author_role=user.role, body=text[:1000], mentions=mentions))
    db.add(DecisionLog(actor=user.email, action="note added", subject=f"candidate:{cand.id}", reason=f"a note of {len(text)} characters was added (the text is kept on the candidate, not in the log, because a note can mention a person)", evidence={"mentions": mentions}))
    db.commit()
    flash(request, "Note saved." + (f" Mentioned: {', '.join(m.split('@')[0] for m in mentions)}." if mentions else ""))
    return RedirectResponse(back, status_code=303)


@router.post("/candidates/{cand_id}/notes/{note_id}/delete")
def delete_note(request: Request, cand_id: int, note_id: int, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    """Only the author deletes their own note; the removal is logged."""
    from app.models_ext import CandidateNote

    note = db.get(CandidateNote, note_id)
    if note is None or note.candidate_id != cand_id:
        raise HTTPException(404, "That note does not exist")
    if note.author != user.email:
        raise HTTPException(403, "Only the author can delete a note")
    db.delete(note)
    db.add(DecisionLog(actor=user.email, action="note deleted", subject=f"candidate:{cand_id}", reason="the author deleted their note"))
    db.commit()
    return RedirectResponse(f"/candidates/{cand_id}#notes", status_code=303)


STEPS = [("Applied", ("APPLIED", "REVIEW", "EXTRACTED")), ("Screened", ("SCREENED",)), ("Shortlisted", ("SHORTLISTED",)), ("AI interview", ("AI_INTERVIEW",)),
         ("Human interview", ("HUMAN_INTERVIEW",)), ("Decision", ("DECISION",))]


def header_context(db: Session, cand: Candidate, is_blind: bool, profile: CandidateProfile, blind) -> dict:
    """What the candidate page header needs: the stage stepper, the next thing a person can do, the CV score and the candidate's own activity."""
    idx = next((i for i, (_l, names) in enumerate(STEPS) if cand.stage in names), -1)
    steps = [{"label": label, "state": "done" if idx > i else ("now" if idx == i else "")} for i, (label, _n) in enumerate(STEPS)]
    nxt = {"SCREENED": ("Approve a shortlist", f"/screening/{cand.requisition_id}"), "SHORTLISTED": ("Invite to the AI interview", "/interviews"),
           "AI_INTERVIEW": ("Review the AI interview", f"/interviews/{cand.id}"), "HUMAN_INTERVIEW": ("Open the copilot", f"/copilot/{cand.id}"),
           "REVIEW": ("Check the unsure fields", "/review")}.get(cand.stage)
    activity = [SimpleNamespace(at=e.at, actor=e.actor, action=e.action, reason=redact_identity(cand, e.reason) if is_blind else e.reason)  # the blind view hides identity here too
                for e in db.scalars(select(DecisionLog).where(DecisionLog.subject == f"candidate:{cand.id}").order_by(DecisionLog.id.desc()).limit(40))]
    display = f"Candidate #{cand.id}" if is_blind else (profile.name.value or f"Candidate #{cand.id}")
    return {"steps": steps, "withdrawn": cand.stage == "WITHDRAWN", "next_action": nxt, "activity": activity, "display_name": display,
            "initial": "#" if is_blind else (display[:1] or "?")}


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
                  score_total=round(sum(r.weight * r.score for r in scores) / 3, 1) if scores else None,
                  **header_context(db, cand, is_blind, profile, make_blind(cand)), **notes_context(db, cand, is_blind or user.role == "hiring_manager"))


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
def pipeline(request: Request, blind: int | None = None, job: int | None = None, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    """The board: one column per stage. A recruiter can drag a card to another column; a box asks for the reason and the supervisor decides if the move is allowed."""
    is_blind = effective_blind(user, blind)
    columns = {s: [] for s in Stage}
    dups = duplicate_map(db)
    from app.models_ext import InterviewSession, ItemScoreRow
    asked = {i.candidate_id for i in db.scalars(select(InterviewSession).where(InterviewSession.status == "PERSON_REQUESTED"))}
    totals: dict[int, float] = {}
    for r in db.scalars(select(ItemScoreRow)):
        totals[r.candidate_id] = totals.get(r.candidate_id, 0.0) + r.weight * r.score / 3
    jobs = list(db.scalars(select(Requisition).order_by(Requisition.id)))
    query = select(Candidate).order_by(Candidate.id)
    if job:
        query = query.where(Candidate.requisition_id == job)
    for c in db.scalars(query):
        p = CandidateProfile.model_validate(c.profile or {})
        label = f"Candidate #{c.id}" if is_blind else (p.name.value or f"Candidate #{c.id}")
        chip = {"id": c.id, "label": label, "title": make_blind(c).current_title if is_blind else p.current_title.value,
                "format": c.cv_format, "dup": dups.get(c.id, []), "person": c.id in asked, "score": round(totals[c.id]) if c.id in totals else None,
                "initial": "#" if is_blind else (label[:1] or "?")}
        columns[Stage(c.stage)].append(chip)
    allowed = {s.value: [(t.value, who) for t, who in moves.items()] for s, moves in ALLOWED.items()}
    return render(request, "pipeline.html", user, columns=columns, is_blind=is_blind, allowed=allowed, stages=[s.value for s in Stage], jobs=jobs, job=job,
                  total=sum(len(v) for v in columns.values()))


@router.post("/pipeline/move")
def pipeline_move(request: Request, candidate_id: int = Form(...), to: str = Form(...), reason: str = Form(""), ajax: int = Form(0),
                  user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """A person moves a candidate. The supervisor refuses anything the table of allowed moves does not permit. The board's drag-and-drop box posts here with ajax=1 and gets JSON back."""
    cand = get_candidate(db, candidate_id)
    ok, message = True, ""
    try:
        frm = cand.stage
        move(db, cand, to, user.email, reason)
    except MoveRefused as e:
        db.rollback()
        ok, message = False, f"Refused: {e}"
    else:
        db.commit()
        message = f"Candidate #{cand.id} moved from {frm} to {to}."
    if ajax:
        from fastapi.responses import JSONResponse

        if ok:
            flash(request, message)  # shown after the board reloads; a refusal is shown in the box instead
        return JSONResponse({"ok": ok, "message": message})
    flash(request, message, "good" if ok else "bad")
    return RedirectResponse("/pipeline", status_code=303)
