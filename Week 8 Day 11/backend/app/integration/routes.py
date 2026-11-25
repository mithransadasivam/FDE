"""Day 8 API: sign-in (/api/auth/…), the Integrations screen (/api/integration/…) and the webhook (/api/hooks/…)."""

import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.integration import auth, service
from app.integration.models import WebhookRejected

router = APIRouter()


# ---------------------------------------------------------------- sign-in to the console
@router.get("/api/auth/login")
def login(request: Request, next: str = "/", origin: str = ""):
    # The screens pass their own origin (http://localhost:5173), because Vite's proxy changes the Host header
    base = origin if re.fullmatch(r"http://(localhost|127\.0\.0\.1)(:\d+)?", origin) else f"http://{request.headers.get('host', 'localhost:8000')}"
    return RedirectResponse(auth.login_url(f"{base}/api/auth/callback", next), status_code=302)


@router.get("/api/auth/callback")
def callback(code: str = "", state: str = "", error: str = ""):
    if error or not code:
        raise HTTPException(400, f"Sign-in did not finish: {error or 'no code'}")
    try:
        sid, nxt = auth.finish(code, state)
    except ValueError as e:
        raise HTTPException(400, str(e))
    r = RedirectResponse(nxt or "/", status_code=302)
    r.set_cookie(auth.COOKIE, sid, httponly=True, samesite="lax")
    return r


@router.get("/api/auth/me")
def me(request: Request):
    s = auth.session(request.cookies.get(auth.COOKIE))
    return {"signed_in": bool(s), **(s["person"] if s else {})}


@router.post("/api/auth/logout")
def logout(request: Request):
    auth.sign_out(request.cookies.get(auth.COOKIE))
    r = JSONResponse({"signed_in": False})
    r.delete_cookie(auth.COOKIE)
    return r


# ---------------------------------------------------------------- the webhook the bank's ticketing system calls
@router.post("/api/hooks/kyc-exceptions")
async def hook(request: Request):
    body = await request.body()
    try:
        return await run_in_threadpool(service.receive_webhook, {k.lower(): v for k, v in request.headers.items()}, body)
    except WebhookRejected as e:
        raise HTTPException(400, str(e))


# ---------------------------------------------------------------- the Integrations screen
class ActRequest(BaseModel):
    person: str
    tool: str
    args: dict = {}


class RaiseRequest(BaseModel):
    team_id: str = "N1"


@router.get("/api/integration/status")
def status():
    return service.status()


@router.get("/api/integration/token-probes")
def token_probes():
    return service.token_probes()


@router.post("/api/integration/act")
def act(body: ActRequest):
    try:
        return service.act(body.person, body.tool, body.args)
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.get("/api/integration/audit")
def audit(system: str = ""):
    return service.audit_log(system)


@router.get("/api/integration/webhooks")
def webhooks():
    return service.webhooks()


@router.post("/api/integration/raise-exception")
def raise_exception(body: RaiseRequest):
    return service.raise_exception(body.team_id)


@router.post("/api/integration/webhook-probes")
def webhook_probes():
    return service.webhook_probes()


@router.get("/api/integration/permissions")
def permissions():
    return service.permissions(run=False)


@router.post("/api/integration/permissions/run")
def permissions_run():
    return service.permissions(run=True)
