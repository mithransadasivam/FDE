"""Passwords, sign-in and role checks (Prompt 3). Staff only: candidates never sign in."""
import re
from datetime import datetime, timedelta, timezone

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


MAX_FAILED = 5  # wrong passwords in a row before the account is locked
LOCK_MINUTES = 15
ROLES = ("hiring_manager", "recruiter", "auditor")  # the auditor is read-only: analytics, the decision log and the audit export


class LoginRefused(Exception):
    """The sign-in was refused for a reason the person should be told (locked or deactivated). The message is safe to show."""


def _aware(dt: datetime | None) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def check_password_policy(password: str, email: str = "") -> list[str]:
    """What is wrong with a new password (empty list = fine): at least 10 characters, a letter and a digit, and not the email."""
    problems = []
    if len(password or "") < 10:
        problems.append("at least 10 characters")
    if not re.search(r"[A-Za-z]", password or "") or not re.search(r"\d", password or ""):
        problems.append("at least one letter and one digit")
    if email and (password or "").lower() in (email.lower(), email.split("@")[0].lower()):
        problems.append("not the same as the email address")
    return problems


def authenticate(db: Session, email: str, password: str) -> User | None:
    """The signed-in user, or None for a wrong email or password. Raises LoginRefused when the account is locked (too many wrong passwords) or deactivated."""
    from app.models import DecisionLog

    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    now = datetime.now(timezone.utc)
    if user is None:
        return None
    locked = _aware(user.locked_until)
    if locked and locked > now:
        raise LoginRefused(f"Too many wrong passwords. This account is locked for {int((locked - now).total_seconds() // 60) + 1} more minute(s).")
    if verify_password(password, user.password_hash):
        if not user.is_active:
            raise LoginRefused("This account has been deactivated. Ask a hiring manager.")
        user.failed_logins, user.locked_until, user.last_login = 0, None, now
        db.commit()
        return user
    user.failed_logins = (user.failed_logins or 0) + 1
    if user.failed_logins >= MAX_FAILED:
        user.failed_logins, user.locked_until = 0, now + timedelta(minutes=LOCK_MINUTES)
        db.add(DecisionLog(actor="system", action="sign-in locked", subject=f"user:{user.id}", reason=f"{MAX_FAILED} wrong passwords in a row: locked for {LOCK_MINUTES} minutes"))
    db.commit()
    return None


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """A dependency: the signed-in person, or a redirect to /login when nobody is signed in."""
    user_id = request.session.get("user_id")
    user = db.get(User, user_id) if user_id else None
    if user is None or not user.is_active:  # a person who has been deactivated is signed out at their next request
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
AUDIT = require_role("hiring_manager", "auditor")  # the audit bundle: the hiring manager and the read-only auditor
INSIGHT = require_role("hiring_manager", "recruiter", "auditor")  # the read-only pages an auditor may use too
