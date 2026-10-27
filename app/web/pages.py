"""Sign-in, home page, health check and the decision log (Prompts 3-4)."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import STAFF, authenticate, current_user
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
    return render(request, "login.html")


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = authenticate(db, email, password)
    if user is None:
        return render(request, "login.html", status_code=401, error="Wrong email or password.", email=email)
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
    return render(request, "home.html", user, counts=counts)


@router.get("/log")
def decision_log(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    entries = db.scalars(select(DecisionLog).order_by(DecisionLog.id.desc()).limit(300)).all()
    return render(request, "log.html", user, entries=entries)
