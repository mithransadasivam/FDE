"""Things every page needs: templates, the role menus, flash messages (Prompts 4-5)."""
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# One place for the menus. Hiding a link is not security: each route also has its own role check.
MENUS = {
    "hiring_manager": [("Requisitions", "/requisitions"), ("Candidates (blind)", "/candidates"),
                       ("Pipeline", "/pipeline"), ("Decision log", "/log")],
    "recruiter": [("Requisitions", "/requisitions"), ("Candidates", "/candidates"),
                  ("Review queue", "/review"), ("Pipeline", "/pipeline"), ("Decision log", "/log")],
}

ROLE_LABELS = {"hiring_manager": "Hiring manager", "recruiter": "Recruiter"}


def flash(request: Request, message: str, kind: str = "good") -> None:
    """Kept in the signed session cookie so it survives the redirect after a form post."""
    request.session.setdefault("_flash", []).append({"text": message, "kind": kind})


def render(request: Request, name: str, user=None, status_code: int = 200, **context):
    messages = request.session.pop("_flash", [])
    context.update(
        user=user,
        menu=MENUS.get(user.role, []) if user else [],
        role_label=ROLE_LABELS.get(user.role, "") if user else "",
        messages=messages,
        path=request.url.path,
    )
    return templates.TemplateResponse(request, name, context, status_code=status_code)
