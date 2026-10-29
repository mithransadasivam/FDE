"""The FastAPI app (Prompt 3 onwards)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.db import init_db
from app.web import admin, assistant, candidates, compliance, copilot, insights, integrations, interview, ops, outbox, pages, public, requisitions, scorecard, screening, trust


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    get_settings().storage_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Hiring Intelligence", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=get_settings().secret_key, same_site="lax", max_age=8 * 3600)
app.mount("/static", StaticFiles(directory=str(Path(__file__).resolve().parent.parent / "static")), name="static")
app.include_router(pages.router)
app.include_router(requisitions.router)
app.include_router(public.router)
app.include_router(candidates.router)
app.include_router(screening.router)
app.include_router(interview.router)
app.include_router(outbox.router)
app.include_router(assistant.router)
app.include_router(copilot.router)
app.include_router(compliance.router)
app.include_router(ops.router)
app.include_router(scorecard.router)
app.include_router(trust.router)
app.include_router(insights.router)
app.include_router(admin.router)
app.include_router(integrations.router)  # candidates' data rights
if get_settings().enable_integrations:  # hidden unless switched on
    app.include_router(integrations.api_router)
app.middleware("http")(ops.count_requests)


@app.exception_handler(HTTPException)
async def friendly_errors(request: Request, exc: HTTPException):
    """Redirects (303) pass through; a 403 or 404 asked for by a browser gets a styled page, everything else the default JSON."""
    from fastapi.exception_handlers import http_exception_handler
    if exc.status_code in (403, 404) and "text/html" in request.headers.get("accept", ""):
        from app.web.common import render
        headline = {403: "That page is not for your role", 404: "We could not find that page"}[exc.status_code]
        return render(request, "error.html", None, status_code=exc.status_code, code=exc.status_code, headline=headline, detail=exc.detail, back="/")
    return await http_exception_handler(request, exc)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Headers every response carries: no sniffing, no framing, no referrer leaks, the camera off and the microphone only for this site, and a content policy
    that only lets the page load scripts, styles and audio from itself."""
    response = await call_next(request)
    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "same-origin")
    h.setdefault("Permissions-Policy", "camera=(), geolocation=(), microphone=(self)")
    h.setdefault("Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
                                            "media-src 'self' blob: data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
    return response
