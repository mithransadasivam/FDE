"""Sign-in, home page, health check and the decision log (Prompts 3-4)."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import STAFF, LoginRefused, authenticate, current_user
from app.config import get_settings
from app.db import get_db
from app.models import Candidate, DecisionLog, Requisition, ReviewItem, User
from app.web.common import flash, render

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/login")
def login_form(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if user_id and db.get(User, user_id):
        return RedirectResponse("/", status_code=303)
    return render(request, "login.html", demo=get_settings().demo_mode)


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    try:
        user = authenticate(db, email, password)
    except LoginRefused as e:
        return render(request, "login.html", status_code=403, error=str(e), email=email, demo=get_settings().demo_mode)
    if user is None:
        return render(request, "login.html", status_code=401, error="Wrong email or password.", email=email, demo=get_settings().demo_mode)
    request.session.clear()
    request.session["user_id"] = user.id
    flash(request, f"Welcome, {user.name}.")
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@router.get("/")
def home(request: Request, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    counts = {
        "Requisitions": db.scalar(select(func.count()).select_from(Requisition)),
        "Published jobs": db.scalar(select(func.count()).select_from(Requisition).where(Requisition.status == "PUBLISHED")),
        "Candidates": db.scalar(select(func.count()).select_from(Candidate)),
        "Fields to review": db.scalar(select(func.count()).select_from(ReviewItem).where(ReviewItem.resolved.is_(False))),
    }
    from app.models_ext import ComplianceFinding, EmailDraft, InterviewSession
    from app.schemas import Stage
    stages = dict(db.execute(select(Candidate.stage, func.count(Candidate.id)).group_by(Candidate.stage)).all())
    funnel = [(s.value, stages[s.value]) for s in Stage if stages.get(s.value)]
    waiting = [("Unsure fields to check", counts["Fields to review"], "/review"),
               ("Candidates scored, shortlist to approve", stages.get("SCREENED", 0), "/screening"),
               ("AI interview scorecards to review", db.scalar(select(func.count(InterviewSession.id)).where(InterviewSession.status == "DONE", InterviewSession.reviewed_by.is_(None))) or 0, "/interviews"),
               ("Email drafts to approve", db.scalar(select(func.count(EmailDraft.id)).where(EmailDraft.status == "DRAFT")) or 0, "/outbox"),
               ("Open compliance findings", db.scalar(select(func.count(ComplianceFinding.id)).where(ComplianceFinding.status == "OPEN")) or 0, "/compliance")]
    recent = db.scalars(select(DecisionLog).order_by(DecisionLog.id.desc()).limit(8)).all()
    from app.models_ext import FinalDecision
    reached = lambda *names: sum(stages.get(n, 0) for n in names)
    steps = [("Create a requisition from a voice note", counts["Requisitions"] > 0, "/requisitions"),
             ("Approve the rubric and publish the job", counts["Published jobs"] > 0, "/requisitions"),
             ("Receive applications", counts["Candidates"] > 0, "/jobs"),
             ("Check the unsure CV fields", counts["Candidates"] > 0 and counts["Fields to review"] == 0, "/review"),
             ("Screen candidates and approve a shortlist", reached("SHORTLISTED", "AI_INTERVIEW", "HUMAN_INTERVIEW", "DECISION") > 0, "/screening"),
             ("Invite someone to the AI interview", bool(db.scalar(select(func.count(InterviewSession.id)))), "/interviews"),
             ("Review a scorecard with your own levels", bool(db.scalar(select(func.count(InterviewSession.id)).where(InterviewSession.reviewed_by.is_not(None)))), "/interviews"),
             ("Record a decision", bool(db.scalar(select(func.count(FinalDecision.id)))), "/scorecard/1")]
    checklist = {"steps": steps, "done": sum(1 for _l, ok, _h in steps if ok)}
    return render(request, "home.html", user, counts=counts, funnel=funnel, total_candidates=sum(stages.values()), waiting=waiting, recent=recent, checklist=checklist)


@router.get("/demo")
def demo(request: Request, user: User = Depends(STAFF)):
    from app.config import get_settings
    return render(request, "demo.html", user, fake=get_settings().fake_models)


@router.get("/log")
def decision_log(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    entries = db.scalars(select(DecisionLog).order_by(DecisionLog.id.desc()).limit(300)).all()
    return render(request, "log.html", user, entries=entries)
