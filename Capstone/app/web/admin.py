"""Administration: company settings, users and roles, your own account and password, and the help page.

Only the hiring manager can change settings and manage users; everything they change is written to the decision log (who, what, when).
"""
import secrets

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import branding
from app.auth import HM, ROLES, check_password_policy, current_user, hash_password, verify_password
from app.db import get_db
from app.models import DecisionLog, User
from app.models_ext import AppSetting
from app.web.common import ROLE_LABELS, flash, render

router = APIRouter()
ROLE_CHOICES = {"hiring_manager": "Hiring manager", "recruiter": "Recruiter", "auditor": "Auditor (read-only)"}
ROLE_LABELS.setdefault("auditor", "Auditor")


# ---- company settings ---------------------------------------------------------------------------------------------------------------------------
@router.get("/settings")
def settings_page(request: Request, user: User = Depends(HM), db: Session = Depends(get_db)):
    return render(request, "settings.html", user, values=branding.load(db), defaults=branding.DEFAULTS)


@router.post("/settings")
async def save_settings(request: Request, user: User = Depends(HM), db: Session = Depends(get_db)):
    form = dict((await request.form()).items())
    values, problems = branding.validate(form)
    if problems:
        flash(request, " ".join(problems), "bad")
        return RedirectResponse("/settings", status_code=303)
    changed = []
    for key, value in values.items():
        row = db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value=value))
            changed.append(key)
        elif row.value != value:
            row.value = value
            changed.append(key)
    db.add(DecisionLog(actor=user.email, action="company settings changed", subject="settings", reason=", ".join(changed) or "nothing changed",
                       evidence={k: values[k] for k in changed}))
    db.commit()
    branding.clear_cache()
    flash(request, "Settings saved." if changed else "Nothing changed.")
    return RedirectResponse("/settings", status_code=303)


# ---- users and roles --------------------------------------------------------------------------------------------------------------------------------
@router.get("/users")
def users_page(request: Request, user: User = Depends(HM), db: Session = Depends(get_db)):
    users = db.scalars(select(User).order_by(User.id)).all()
    return render(request, "users.html", user, users=users, role_choices=ROLE_CHOICES, new_password=request.session.pop("_new_password", None))


@router.post("/users")
def create_user(request: Request, name: str = Form(""), email: str = Form(""), role: str = Form(""), password: str = Form(""),
                user: User = Depends(HM), db: Session = Depends(get_db)):
    email = email.strip().lower()
    problems = []
    if not name.strip():
        problems.append("Enter the person's name.")
    if "@" not in email or "." not in email.split("@")[-1]:
        problems.append("Enter a valid email address.")
    if role not in ROLES:
        problems.append("Choose a role.")
    if db.scalar(select(User).where(User.email == email)):
        problems.append("That email already has an account.")
    generated = not password
    password = password or (secrets.token_urlsafe(9) + "7a")
    bad = check_password_policy(password, email)
    if bad:
        problems.append("The password needs " + ", ".join(bad) + ".")
    if problems:
        flash(request, " ".join(problems), "bad")
        return RedirectResponse("/users", status_code=303)
    new = User(email=email, name=name.strip(), role=role, password_hash=hash_password(password))
    db.add(new)
    db.add(DecisionLog(actor=user.email, action="user created", subject=f"user:{email}", reason=f"role {role}"))
    db.commit()
    if generated:
        request.session["_new_password"] = {"email": email, "password": password}  # shown once
    flash(request, f"Account created for {email}.")
    return RedirectResponse("/users", status_code=303)


def _target(db: Session, me: User, user_id: int) -> User:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, "That user does not exist")
    if target.id == me.id:
        raise HTTPException(400, "You cannot change your own access here: ask another hiring manager.")
    return target


@router.post("/users/{user_id}/active")
def set_active(request: Request, user_id: int, active: str = Form(""), user: User = Depends(HM), db: Session = Depends(get_db)):
    target = _target(db, user, user_id)
    target.is_active = active == "1"
    db.add(DecisionLog(actor=user.email, action="user reactivated" if target.is_active else "user deactivated", subject=f"user:{target.email}",
                       reason="their past decisions stay in the log"))
    db.commit()
    flash(request, f"{target.email} is now {'active' if target.is_active else 'deactivated'}.")
    return RedirectResponse("/users", status_code=303)


@router.post("/users/{user_id}/role")
def set_role(request: Request, user_id: int, role: str = Form(""), user: User = Depends(HM), db: Session = Depends(get_db)):
    target = _target(db, user, user_id)
    if role not in ROLES:
        flash(request, "Choose a role.", "bad")
    else:
        db.add(DecisionLog(actor=user.email, action="user role changed", subject=f"user:{target.email}", reason=f"{target.role} -> {role}"))
        target.role = role
        db.commit()
        flash(request, f"{target.email} is now {ROLE_CHOICES[role]}.")
    return RedirectResponse("/users", status_code=303)


@router.post("/users/{user_id}/reset")
def reset_password(request: Request, user_id: int, user: User = Depends(HM), db: Session = Depends(get_db)):
    target = _target(db, user, user_id)
    temp = secrets.token_urlsafe(9) + "7a"
    target.password_hash, target.failed_logins, target.locked_until = hash_password(temp), 0, None
    db.add(DecisionLog(actor=user.email, action="password reset", subject=f"user:{target.email}", reason="a temporary password was issued"))
    db.commit()
    request.session["_new_password"] = {"email": target.email, "password": temp}
    return RedirectResponse("/users", status_code=303)


# ---- your own account --------------------------------------------------------------------------------------------------------------------------------
@router.get("/account")
def account_page(request: Request, user: User = Depends(current_user)):
    return render(request, "account.html", user)


@router.post("/account/password")
def change_password(request: Request, current: str = Form(""), new: str = Form(""), again: str = Form(""), user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(current, user.password_hash):
        flash(request, "Your current password is not right.", "bad")
    elif new != again:
        flash(request, "The two new passwords are not the same.", "bad")
    elif check_password_policy(new, user.email):
        flash(request, "The new password needs " + ", ".join(check_password_policy(new, user.email)) + ".", "bad")
    else:
        user.password_hash = hash_password(new)
        db.add(DecisionLog(actor=user.email, action="password changed", subject=f"user:{user.email}", reason="changed by the user"))
        db.commit()
        flash(request, "Your password was changed.")
    return RedirectResponse("/account", status_code=303)


# ---- help --------------------------------------------------------------------------------------------------------------------------------------------------
@router.get("/help")
def help_page(request: Request, user: User = Depends(current_user)):
    return render(request, "help.html", user)
