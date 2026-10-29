"""Company settings and branding: the name, tagline, accent colour and contact shown across the app. Stored in the database, changed by the hiring
manager on the Settings page, cached for a few seconds so a page render does not hit the database for every request."""
import re
import time

DEFAULTS = {
    "company_name": "Hiring Intelligence",
    "tagline": "Agents prepare · people decide",
    "accent": "#4f46e5",
    "support_email": "careers@example.com",
    "welcome": "Fair, explainable hiring. AI helps read applications; people make every decision.",
}
_cache: dict = {"at": 0.0, "values": None}
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def clear_cache() -> None:
    _cache["at"], _cache["values"] = 0.0, None


def load(db=None) -> dict:
    """The current settings (defaults for anything not saved)."""
    if _cache["values"] is not None and time.monotonic() - _cache["at"] < 5:
        return _cache["values"]
    from app.db import SessionLocal
    from app.models_ext import AppSetting

    values = dict(DEFAULTS)
    try:
        own = db is None
        session = SessionLocal() if own else db
        try:
            for row in session.query(AppSetting).all():
                if row.key in DEFAULTS and row.value:
                    values[row.key] = row.value
        finally:
            if own:
                session.close()
    except Exception:  # a database that is not ready must never stop a page from showing
        pass
    _cache["at"], _cache["values"] = time.monotonic(), values
    return values


def validate(form: dict) -> tuple[dict, list[str]]:
    """Cleans what the hiring manager typed. Returns the values to save and the problems to show."""
    out, problems = {}, []
    name = (form.get("company_name") or "").strip()
    if not 2 <= len(name) <= 60:
        problems.append("The company name must be 2 to 60 characters.")
    out["company_name"] = name
    out["tagline"] = (form.get("tagline") or "").strip()[:100]
    accent = (form.get("accent") or "").strip()
    if not HEX.match(accent):
        problems.append("The accent colour must look like #4f46e5.")
    out["accent"] = accent
    email = (form.get("support_email") or "").strip()
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        problems.append("The support email does not look like an email address.")
    out["support_email"] = email
    out["welcome"] = (form.get("welcome") or "").strip()[:240]
    return out, problems
