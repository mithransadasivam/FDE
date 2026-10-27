"""The FastAPI app (Prompt 3 onwards)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.db import init_db
from app.web import assistant, candidates, compliance, copilot, interview, ops, outbox, pages, public, requisitions, scorecard, screening, trust


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    get_settings().storage_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Hiring Intelligence", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=get_settings().secret_key, same_site="lax", max_age=8 * 3600)
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
app.middleware("http")(ops.count_requests)


@app.exception_handler(HTTPException)
async def friendly_errors(request: Request, exc: HTTPException):
    """Redirects (303) pass through; everything else gets a readable page or JSON."""
    from fastapi.exception_handlers import http_exception_handler
    if exc.status_code in (403, 404) and "text/html" in request.headers.get("accept", ""):
        body = (f"<!doctype html><title>{exc.status_code}</title><body style='font-family:sans-serif;margin:3rem'>"
                f"<h2>{exc.status_code}</h2><p>{exc.detail}</p><p><a href='/'>Back to the console</a></p></body>")
        return HTMLResponse(body, status_code=exc.status_code)
    return await http_exception_handler(request, exc)
