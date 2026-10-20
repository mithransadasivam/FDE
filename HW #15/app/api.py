"""Day 15: the chatbot as a web API, with FastAPI.

    uvicorn app.api:api --reload                  (on your laptop, http://localhost:8000)
    CHAT_FAKE=1 uvicorn app.api:api --reload      (the fake chatbot: no Ollama, no key)

Endpoints:  GET /           a small chat page that uses /ask/stream
            GET /docs       the API's own documentation, where you can try every endpoint
            GET /health     "the process is alive"         GET /ready    "it can answer questions"
            POST /ask       one answer as JSON              POST /ask/stream   the answer as it is written
            GET /metrics    the numbers behind              GET /dashboard     the monitoring page

Done: everything, including ask() (Activity 1, checked by tests/test_api.py).
"""

import json
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app import service
from app.monitoring import (
    check_alerts,
    load_rules,
    log_request,
    read_requests,
    summarise,
)
from app.reliability import ModelUnavailable
from app.tracing import setup_tracing

UNAVAILABLE = "The chatbot cannot reach its language models right now. Please try again in a few minutes."
STATIC = Path(__file__).parent / "static"

setup_tracing()
api = FastAPI(
    title="IT policy chatbot",
    version="1.0",
    description="Answers questions from the IT policy documents, with sources.",
)


class AskRequest(BaseModel):
    question: str = Field(
        min_length=1, max_length=4000, examples=["How long can a VPN session last?"]
    )


class AskResponse(BaseModel):
    request_id: str
    answer: str
    sources: list[str]
    declined: bool
    model: str | None
    fallback: bool
    seconds: float


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


@api.post("/ask", response_model=AskResponse)
def ask(body: AskRequest) -> AskResponse:
    """Answer one question as JSON.

    FastAPI has already checked the body: an empty question, or one over 4000 characters, gets a
    422 reply before this function runs.

    Rules (tests/test_api.py checks each one):
    - request_id = new_request_id(); start = time.perf_counter()
    - result = service.answer(body.question)
      ModelUnavailable error: log_request(request_id=request_id, status="error", error=str(error),
          seconds=<time so far, rounded to 3 places>), then raise HTTPException(503, detail=UNAVAILABLE)
    - seconds = round(time.perf_counter() - start, 3)
    - log_request(request_id=request_id, status="ok", seconds=seconds, model=result["model"],
          fallback=result["fallback"], tokens=result["tokens"], declined=result["declined"])
    - return AskResponse(request_id=..., seconds=..., and answer, sources, declined, model,
          fallback from result)
    """
    request_id, start = new_request_id(), time.perf_counter()
    try:
        result = service.answer(body.question)
    except ModelUnavailable as error:
        log_request(
            request_id=request_id,
            status="error",
            error=str(error),
            seconds=round(time.perf_counter() - start, 3),
        )
        raise HTTPException(503, detail=UNAVAILABLE) from error
    seconds = round(time.perf_counter() - start, 3)
    log_request(
        request_id=request_id,
        status="ok",
        seconds=seconds,
        model=result["model"],
        fallback=result["fallback"],
        tokens=result["tokens"],
        declined=result["declined"],
    )
    return AskResponse(
        request_id=request_id,
        seconds=seconds,
        answer=result["answer"],
        sources=result["sources"],
        declined=result["declined"],
        model=result["model"],
        fallback=result["fallback"],
    )


@api.post("/ask/stream")
def ask_stream(body: AskRequest):
    """The answer as it is written, as server-sent events: {"type": "token", "text": ...} lines,
    then {"type": "done", "sources": [...], ...}."""
    request_id, start = new_request_id(), time.perf_counter()
    try:
        p = service.prepare(body.question)
    except ModelUnavailable as error:
        log_request(
            request_id=request_id,
            status="error",
            error=str(error),
            seconds=round(time.perf_counter() - start, 3),
        )
        raise HTTPException(503, detail=UNAVAILABLE) from error

    def events():
        text = ""
        for piece in p["pieces"]:
            text += piece
            yield f"data: {json.dumps({'type': 'token', 'text': piece})}\n\n"
        seconds = round(time.perf_counter() - start, 3)
        declined = text.strip() == service.DECLINE
        log_request(
            request_id=request_id,
            status="ok",
            seconds=seconds,
            model=p["model"],
            fallback=p["fallback"],
            tokens=p["usage"].get("tokens"),
            declined=declined,
        )
        done = {
            "type": "done",
            "request_id": request_id,
            "sources": p["sources"],
            "model": p["model"],
            "fallback": p["fallback"],
            "seconds": seconds,
        }
        yield f"data: {json.dumps(done)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@api.get("/health")
def health():
    """Liveness: the process is running. Docker restarts the container if this stops answering."""
    return {"status": "ok"}


@api.get("/ready")
def ready():
    """Readiness: everything the chatbot needs is there. 503 until it is."""
    result = service.readiness()
    return JSONResponse(result, status_code=200 if result["ready"] else 503)


@api.get("/metrics")
def metrics():
    summary = summarise(read_requests())
    summary["alerts"] = check_alerts(summary, load_rules())
    summary["prompt_version"] = service.PROMPT_VERSION
    summary["models"] = service.models()
    return summary


@api.get("/", include_in_schema=False)
def chat_page():
    return FileResponse(STATIC / "index.html")


@api.get("/dashboard", include_in_schema=False)
def dashboard_page():
    return FileResponse(STATIC / "dashboard.html")
