"""The chatbot as a web API, with FastAPI (Day 15), with Day 16's cache, routes and costs.

    uvicorn app.api:api --reload                  (on your laptop, http://localhost:8000)
    CHAT_FAKE=1 uvicorn app.api:api --reload      (the fake chatbot: no Ollama, no key)

Endpoints:  GET /           a small chat page that uses /ask/stream
            GET /docs       the API's own documentation, where you can try every endpoint
            GET /health     "the process is alive"         GET /ready    "it can answer questions"
            POST /ask       one answer as JSON              POST /ask/stream   the answer as it is written
            GET /metrics    the numbers behind              GET /dashboard     the monitoring page
            POST /cache/clear   empty the response cache (Day 16)

Day 16 replaced this file: it contains the finished Day 15 code, and every answer now also
reports its route, its tokens, its cost and whether it came from the cache. Nothing is a TODO.
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
from app.perf import summarise_extra
from app.reliability import ModelUnavailable
from app.tracing import setup_tracing

UNAVAILABLE = "The chatbot cannot reach its language models right now. Please try again in a few minutes."
STATIC = Path(__file__).parent / "static"
LOGGED = [
    "model",
    "fallback",
    "tokens",
    "prompt_tokens",
    "completion_tokens",
    "cost_usd",
    "route",
    "cached",
    "declined",
]

setup_tracing()
api = FastAPI(
    title="IT policy chatbot",
    version="1.1",
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
    route: str | None = None
    cached: bool = False
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float = 0.0


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def log_error(request_id: str, start: float, error: Exception) -> None:
    log_request(
        request_id=request_id,
        status="error",
        error=str(error),
        seconds=round(time.perf_counter() - start, 3),
    )


@api.post("/ask", response_model=AskResponse)
def ask(body: AskRequest) -> AskResponse:
    """One answer as JSON (Day 15, Activity 1), with its route, tokens, cost and cache status."""
    request_id, start = new_request_id(), time.perf_counter()
    try:
        result = service.answer(body.question)
    except ModelUnavailable as error:
        log_error(request_id, start, error)
        raise HTTPException(503, detail=UNAVAILABLE) from error
    seconds = round(time.perf_counter() - start, 3)
    log_request(
        request_id=request_id,
        status="ok",
        seconds=seconds,
        **{k: result.get(k) for k in LOGGED},
    )
    return AskResponse(
        request_id=request_id,
        seconds=seconds,
        **{k: v for k, v in result.items() if k in AskResponse.model_fields},
    )


@api.post("/ask/stream")
def ask_stream(body: AskRequest):
    """The answer as it is written, as server-sent events: {"type": "token", "text": ...} lines,
    then {"type": "done", "sources": [...], ...}. A cached answer arrives as a single token."""
    request_id, start = new_request_id(), time.perf_counter()
    hit = service.from_cache(body.question)
    if hit is None:
        try:
            p = service.prepare(body.question)
        except ModelUnavailable as error:
            log_error(request_id, start, error)
            raise HTTPException(503, detail=UNAVAILABLE) from error

    def events():
        if hit is not None:
            result = hit
            yield f"data: {json.dumps({'type': 'token', 'text': hit['answer']})}\n\n"
        else:
            text = ""
            for piece in p["pieces"]:
                text += piece
                yield f"data: {json.dumps({'type': 'token', 'text': piece})}\n\n"
            result = service.finish(p, text.strip())
            service.save_to_cache(body.question, result)
        seconds = round(time.perf_counter() - start, 3)
        log_request(
            request_id=request_id,
            status="ok",
            seconds=seconds,
            **{k: result.get(k) for k in LOGGED},
        )
        done = {
            "type": "done",
            "request_id": request_id,
            "sources": result["sources"],
            "model": result["model"],
            "fallback": result["fallback"],
            "route": result["route"],
            "cached": result["cached"],
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
    records = read_requests()
    summary = summarise(records)
    summary["alerts"] = check_alerts(summary, load_rules())
    summary["prompt_version"] = service.PROMPT_VERSION
    summary["models"] = service.models()
    summary.update(summarise_extra(records))
    summary["settings"] = {
        "cache": service.cache_on(),
        "routing": service.routing_on(),
        "small_model": service.models("small")[0],
    }
    return summary


@api.post("/cache/clear")
def clear_cache():
    """Empty the response cache: after changing documents, or before a fair load test."""
    return {"removed": service.get_cache().clear()}


@api.get("/", include_in_schema=False)
def chat_page():
    return FileResponse(STATIC / "index.html")


@api.get("/dashboard", include_in_schema=False)
def dashboard_page():
    return FileResponse(STATIC / "dashboard.html")
