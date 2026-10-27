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
    # Reassign (not append in place): the session only notices changes to its top-level keys.
    request.session["_flash"] = [*request.session.get("_flash", []), {"text": message, "kind": kind}]


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
