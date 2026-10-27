"""Passwords, sign-in and role checks (Prompt 3). Staff only: candidates never sign in."""
import bcrypt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user and verify_password(password, user.password_hash):
        return user
    return None


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """A dependency: the signed-in person, or a redirect to /login when nobody is signed in."""
    user_id = request.session.get("user_id")
    user = db.get(User, user_id) if user_id else None
    if user is None:
        request.session.clear()
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


def require_role(*roles: str):
    """A dependency: the page is only for these roles. Everyone else gets 403."""

    def check(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Your role cannot use this page")
        return user

    return check


HM = require_role("hiring_manager")
RECRUITER = require_role("recruiter")
STAFF = require_role("hiring_manager", "recruiter")
