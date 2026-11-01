"""Things every page needs: templates, the role menus, flash messages (Prompts 4-5)."""
import re
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app import branding

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# One place for the menus. Hiding a link is not security: each route also has its own role check.
# The sidebar is short on purpose. Related pages share a tab bar (see TAB_SETS), so nothing was removed: it was grouped.
MENUS = {
    "hiring_manager": [("Jobs", "/requisitions"), ("Candidates (blind)", "/candidates"), ("Screening", "/screening"), ("Interviews", "/interviews"), ("Assistant", "/assistant"),
                       ("Insights", "/analytics"), ("Users", "/users"), ("Integrations", "/integrations"), ("Settings", "/settings"), ("Account", "/account"), ("Help", "/help")],
    "recruiter": [("Jobs", "/requisitions"), ("Candidates", "/candidates"), ("Screening", "/screening"), ("Interviews", "/interviews"), ("Copilot", "/copilot"),
                  ("Assistant", "/assistant"), ("Inbox", "/inbox"), ("Insights", "/analytics"), ("Account", "/account"), ("Help", "/help")],
    "auditor": [("Insights", "/analytics"), ("Account", "/account"), ("Help", "/help")],
}

ROLE_LABELS = {"hiring_manager": "Hiring manager", "recruiter": "Recruiter", "auditor": "Auditor"}

# How the sidebar groups the menu, and the icon for each link (the icons are in templates/base.html)
NAV_GROUPS = [("Hiring", ["/requisitions", "/candidates", "/screening"]), ("Interviews", ["/interviews", "/copilot"]), ("Work", ["/assistant", "/inbox"]),
              ("Insights", ["/analytics"]), ("Admin", ["/users", "/integrations", "/settings"])]
FOOTER_LINKS = ["/account", "/help"]  # shown in the user menu, not the sidebar
ICONS = {"/requisitions": "i-doc", "/candidates": "i-users", "/screening": "i-target", "/analytics": "i-chart", "/users": "i-users", "/integrations": "i-inbox", "/settings": "i-gear",
         "/account": "i-user", "/help": "i-help", "/interviews": "i-mic", "/copilot": "i-headset", "/assistant": "i-chat", "/inbox": "i-mail"}

# Pages that belong to a menu item although their address is different (so the item stays highlighted, and the tab bar shows)
TAB_SETS = {
    "candidates": {"home": "/candidates", "tabs": [("List", "/candidates"), ("Board", "/pipeline"), ("Compare", "/compare")], "roles": {"recruiter", "hiring_manager"}},
    "inbox": {"home": "/inbox", "tabs": [("Overview", "/inbox"), ("Emails to approve", "/outbox"), ("Fields to check", "/review"), ("Deletions", "/data-requests")], "roles": {"recruiter"}},
    "insights": {"home": "/analytics", "tabs": [("Analytics", "/analytics"), ("Trust & cost", "/trust"), ("Compliance", "/compliance"), ("Decision log", "/log")], "roles": {"recruiter", "hiring_manager", "auditor"}},
}
AUDITOR_TABS = {"/analytics", "/log"}
TAB_BADGES = {"/outbox": "drafts", "/review": "fields"}


def grouped_menu(menu: list[tuple[str, str]]) -> list[tuple[str, list[tuple[str, str, str]]]]:
    by_href = dict((href, label) for label, href in menu)
    out = []
    for group, hrefs in NAV_GROUPS:
        items = [(by_href[h], h, ICONS.get(h, "i-doc")) for h in hrefs if h in by_href]
        if items:
            out.append((group, items))
    return out


def active_href(path: str, menu: list[tuple[str, str]]) -> str:
    """Which sidebar item the current page belongs to (a tab page highlights the item that owns the tab bar)."""
    for ts in TAB_SETS.values():
        if any(path == h or path.startswith(h + "/") for _l, h in ts["tabs"]):
            if any(href == ts["home"] for _l, href in menu):
                return ts["home"]
    hrefs = sorted((h for _l, h in menu), key=len, reverse=True)
    if path.startswith("/jobs"):
        return "/requisitions"
    return next((h for h in hrefs if path == h or path.startswith(h + "/")), "")


def tab_bar(path: str, role: str, badges: dict) -> dict | None:
    for key, ts in TAB_SETS.items():
        if role in ts["roles"] and any(path == h or path.startswith(h + "/") for _l, h in ts["tabs"]):
            tabs = [(label, href, badges.get(TAB_BADGES.get(href, ""), 0)) for label, href in ts["tabs"] if role != "auditor" or href in AUDITOR_TABS]
            if len(tabs) > 1:
                return {"key": key, "tabs": tabs, "current": next((h for _l, h, _b in sorted(tabs, key=lambda t: -len(t[1])) if path == h or path.startswith(h + "/")), "")}
    return None


def waiting_counts() -> dict:
    """What is waiting for a person, for the bell and the tab badges. Cheap counts; never lets a page fail."""
    try:
        from sqlalchemy import func, select

        from app.db import SessionLocal
        from app.models import ReviewItem
        from app.models_ext import ComplianceFinding, DataRequest, EmailDraft, InterviewSession

        with SessionLocal() as db:
            n = lambda q: db.scalar(q) or 0  # noqa: E731
            return {"drafts": n(select(func.count(EmailDraft.id)).where(EmailDraft.status == "DRAFT")),
                    "fields": n(select(func.count(ReviewItem.id)).where(ReviewItem.resolved.is_(False))),
                    "scorecards": n(select(func.count(InterviewSession.id)).where(InterviewSession.status == "DONE", InterviewSession.reviewed_by.is_(None))),
                    "findings": n(select(func.count(ComplianceFinding.id)).where(ComplianceFinding.status == "OPEN"))}
    except Exception:
        return {"drafts": 0, "fields": 0, "requests": 0, "scorecards": 0, "findings": 0}


def flash(request: Request, message: str, kind: str = "good") -> None:
    """Kept in the signed session cookie so it survives the redirect after a form post."""
    # Reassign (not append in place): the session only notices changes to its top-level keys.
    request.session["_flash"] = [*request.session.get("_flash", []), {"text": message, "kind": kind}]


def render(request: Request, name: str, user=None, status_code: int = 200, **context):
    messages = request.session.pop("_flash", [])
    from app.config import get_settings

    menu = [m for m in MENUS.get(user.role, []) if get_settings().enable_integrations or m[1] != "/integrations"] if user else []  # hidden unless switched on
    badges = waiting_counts() if user and user.role in ("recruiter", "hiring_manager") else {}
    items = []
    if user and user.role == "recruiter":
        items = [(f"{badges['drafts']} email draft(s) to approve", "/outbox", badges["drafts"]), (f"{badges['fields']} unsure CV field(s) to check", "/review", badges["fields"]),
                 (f"{badges['scorecards']} AI interview scorecard(s) to review", "/interviews", badges["scorecards"]),
                 (f"{badges['findings']} open compliance finding(s)", "/compliance", badges["findings"])]
    context.update(
        user=user,
        menu=menu,
        nav_groups=grouped_menu(menu) if user else [],
        active_href=active_href(request.url.path, menu) if user else "",
        tab_bar=tab_bar(request.url.path, user.role, badges) if user else None,
        notifications=[i for i in items if i[2]],
        notification_count=sum(i[2] for i in items),
        initials=("".join(w[0] for w in user.name.split(" (")[0].split()[:2]).upper() if user else ""),
        role_label=ROLE_LABELS.get(user.role, "") if user else "",
        messages=messages,
        brand=branding.load(),
        path=request.url.path,
    )
    return templates.TemplateResponse(request, name, context, status_code=status_code)


# ---- uploads (Prompt 5) -----------------------------------------------------------------------------
import uuid  # noqa: E402

from fastapi import HTTPException, UploadFile  # noqa: E402

from app.config import get_settings  # noqa: E402


async def save_upload(upload: UploadFile, folder: str, allowed: set[str], max_bytes: int) -> Path:
    """Check the type and size, then save under a random name. The user's file name is never used on disk."""
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, f"File type {suffix or '(none)'} is not accepted. Please use one of: {', '.join(sorted(allowed))}")
    data = await upload.read()
    if not data:
        raise HTTPException(400, "The file is empty")
    if len(data) > max_bytes:
        raise HTTPException(400, f"The file is larger than {max_bytes // (1024 * 1024)} MB")
    target_dir = get_settings().storage_dir / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{uuid.uuid4().hex}{suffix}"
    target.write_bytes(data)
    return target


templates.env.filters["reqid"] = lambda n: f"REQ-{int(n):03d}"


def _mentions(text: str):
    """Escape a note, then highlight @mentions."""
    from markupsafe import Markup, escape

    return Markup(re.sub(r"(@[A-Za-z0-9_.-]{2,40})", r'<span class="mention">\1</span>', str(escape(text or "")))).replace("\n", Markup("<br>"))


templates.env.filters["mentions"] = _mentions
