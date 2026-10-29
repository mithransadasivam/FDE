"""Things every page needs: templates, the role menus, flash messages (Prompts 4-5)."""
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app import branding

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# One place for the menus. Hiding a link is not security: each route also has its own role check.
MENUS = {
    "hiring_manager": [("Requisitions", "/requisitions"), ("Candidates (blind)", "/candidates"),
                       ("Screening", "/screening"), ("Interviews", "/interviews"), ("Compliance", "/compliance"), ("Assistant", "/assistant"), ("Pipeline", "/pipeline"), ("Compare", "/compare"), ("Analytics", "/analytics"), ("Trust & cost", "/trust"), ("Decision log", "/log"), ("Users", "/users"), ("Integrations", "/integrations"), ("Settings", "/settings"), ("Account", "/account"), ("Help", "/help"), ("Demo mode", "/demo")],
    "recruiter": [("Requisitions", "/requisitions"), ("Candidates", "/candidates"),
                  ("Review queue", "/review"), ("Data requests", "/data-requests"), ("Screening", "/screening"), ("Interviews", "/interviews"),
                  ("Copilot", "/copilot"), ("Outbox", "/outbox"), ("Compliance", "/compliance"), ("Assistant", "/assistant"), ("Pipeline", "/pipeline"), ("Compare", "/compare"), ("Analytics", "/analytics"), ("Trust & cost", "/trust"), ("Decision log", "/log"), ("Account", "/account"), ("Help", "/help"), ("Demo mode", "/demo")],
    "auditor": [("Analytics", "/analytics"), ("Decision log", "/log"), ("Account", "/account"), ("Help", "/help")],
}

ROLE_LABELS = {"hiring_manager": "Hiring manager", "recruiter": "Recruiter"}

# How the sidebar groups the menu, and the icon for each link (the icons are in templates/base.html)
NAV_GROUPS = [("Hiring", ["/requisitions", "/candidates", "/review", "/data-requests", "/screening", "/compare"]), ("Interviews", ["/interviews", "/copilot"]),
              ("Assist", ["/assistant", "/outbox"]), ("Control", ["/pipeline", "/analytics", "/compliance", "/trust", "/log", "/demo"]), ("Admin", ["/users", "/integrations", "/settings", "/account", "/help"])]
ICONS = {"/requisitions": "i-doc", "/candidates": "i-users", "/review": "i-check", "/screening": "i-target", "/compare": "i-users", "/analytics": "i-chart", "/users": "i-users", "/integrations": "i-inbox", "/data-requests": "i-shield", "/settings": "i-gear", "/account": "i-user", "/help": "i-help", "/interviews": "i-mic", "/copilot": "i-headset",
         "/assistant": "i-chat", "/outbox": "i-mail", "/pipeline": "i-board", "/compliance": "i-shield", "/trust": "i-chart", "/log": "i-log", "/demo": "i-play"}


def grouped_menu(menu: list[tuple[str, str]]) -> list[tuple[str, list[tuple[str, str, str]]]]:
    by_href = dict((href, label) for label, href in menu)
    out = []
    for group, hrefs in NAV_GROUPS:
        items = [(by_href[h], h, ICONS.get(h, "i-doc")) for h in hrefs if h in by_href]
        if items:
            out.append((group, items))
    return out


def flash(request: Request, message: str, kind: str = "good") -> None:
    """Kept in the signed session cookie so it survives the redirect after a form post."""
    # Reassign (not append in place): the session only notices changes to its top-level keys.
    request.session["_flash"] = [*request.session.get("_flash", []), {"text": message, "kind": kind}]


def render(request: Request, name: str, user=None, status_code: int = 200, **context):
    messages = request.session.pop("_flash", [])
    from app.config import get_settings

    menu = [m for m in MENUS.get(user.role, []) if get_settings().enable_integrations or m[1] != "/integrations"] if user else []  # hidden unless switched on
    context.update(
        user=user,
        menu=menu,
        nav_groups=grouped_menu(menu) if user else [],
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
