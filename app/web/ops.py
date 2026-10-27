"""Operations endpoints: /ready (can it serve?) and /metrics (Prometheus text format). /health is in pages.py."""
import time
from collections import Counter

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import func, select, text

from app.agents import assistant
from app.config import get_settings
from app.db import OpsSession, SessionLocal
from app.models import Candidate, DecisionLog
from app.models_ext import AgentTrace, ComplianceFinding, EmailDraft, ModelCall, OutboxLog

router = APIRouter()
STARTED = time.time()
HTTP = Counter()  # (method, group, status) -> count
LATENCY = {"sum": 0.0, "count": 0}


def group(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    return "/" + parts[0] if parts else "/"


async def count_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    HTTP[(request.method, group(request.url.path), response.status_code)] += 1
    LATENCY["sum"] += time.perf_counter() - start
    LATENCY["count"] += 1
    return response


@router.get("/ready")
def ready():
    """Ready means: both databases answer, the agent tools are registered, the starter kit is present, and a model (or fake mode) is configured."""
    from app import tools
    from app.agents.base import TOOLS
    checks = {}
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {type(e).__name__}"
    try:
        with OpsSession() as ops:
            ops.execute(text("SELECT 1"))
        checks["ops_database"] = "ok"
    except Exception as e:
        checks["ops_database"] = f"error: {type(e).__name__}"
    tools.load()
    checks["agent_tools"] = f"{len(TOOLS)} registered" if len(TOOLS) >= 25 else "error: tools missing"
    s = get_settings()
    checks["starter_kit"] = "ok" if (s.kit_dir / "question_bank.json").exists() else "error: question bank missing"
    checks["models"] = "fake mode" if s.fake_models else ("ok" if s.openrouter_api_key else "error: no OPENROUTER_API_KEY")
    ok = all(not v.startswith("error") for v in checks.values())
    return JSONResponse({"status": "ready" if ok else "not ready", "checks": checks}, status_code=200 if ok else 503)


def _line(name: str, value, labels: dict | None = None) -> str:
    lab = "{" + ",".join(f'{k}="{v}"' for k, v in labels.items()) + "}" if labels else ""
    return f"{name}{lab} {value}"


@router.get("/metrics", response_class=PlainTextResponse)
def metrics():
    out = ["# HELP hiring_uptime_seconds Seconds since the API started", "# TYPE hiring_uptime_seconds gauge", _line("hiring_uptime_seconds", round(time.time() - STARTED, 1))]
    out += ["# TYPE hiring_http_requests_total counter"]
    out += [_line("hiring_http_requests_total", n, {"method": m, "path": g, "status": s}) for (m, g, s), n in sorted(HTTP.items())]
    out += ["# TYPE hiring_http_request_seconds_sum counter", _line("hiring_http_request_seconds_sum", round(LATENCY["sum"], 4)),
            _line("hiring_http_request_seconds_count", LATENCY["count"])]
    with OpsSession() as ops:
        calls, cost, tin, tout, cached = ops.execute(select(func.count(ModelCall.id), func.coalesce(func.sum(ModelCall.cost_usd), 0), func.coalesce(func.sum(ModelCall.tokens_in), 0),
                                                            func.coalesce(func.sum(ModelCall.tokens_out), 0), func.coalesce(func.sum(ModelCall.cached.cast(type_=__import__("sqlalchemy").Integer)), 0))).one()
        by_tier = ops.execute(select(ModelCall.tier, func.count(ModelCall.id), func.sum(ModelCall.cost_usd)).group_by(ModelCall.tier)).all()
        steps = ops.execute(select(AgentTrace.agent, func.count(AgentTrace.id)).group_by(AgentTrace.agent)).all()
        errors = ops.scalar(select(func.count(AgentTrace.id)).where(AgentTrace.status != "ok")) or 0
    out += ["# TYPE hiring_model_calls_total counter", _line("hiring_model_calls_total", calls), _line("hiring_model_cache_hits_total", cached),
            _line("hiring_model_tokens_in_total", tin), _line("hiring_model_tokens_out_total", tout), _line("hiring_model_cost_usd_total", round(cost, 6))]
    out += [_line("hiring_model_calls_by_tier", n, {"tier": t or "none"}) for t, n, _ in by_tier]
    out += ["# TYPE hiring_agent_steps_total counter"] + [_line("hiring_agent_steps_total", n, {"agent": a}) for a, n in steps]
    out += [_line("hiring_agent_errors_total", errors)]
    with SessionLocal() as db:
        stages = db.execute(select(Candidate.stage, func.count(Candidate.id)).group_by(Candidate.stage)).all()
        out += ["# TYPE hiring_candidates gauge"] + [_line("hiring_candidates", n, {"stage": s}) for s, n in stages]
        out += [_line("hiring_open_findings", db.scalar(select(func.count(ComplianceFinding.id)).where(ComplianceFinding.status == "OPEN")) or 0),
                _line("hiring_email_drafts_waiting", db.scalar(select(func.count(EmailDraft.id)).where(EmailDraft.status == "DRAFT")) or 0),
                _line("hiring_emails_sent_total", db.scalar(select(func.count(OutboxLog.id))) or 0),
                _line("hiring_decision_log_entries", db.scalar(select(func.count(DecisionLog.id))) or 0)]
    out += [_line("hiring_assistant_questions_total", assistant.STATS["asked"]), _line("hiring_assistant_cache_hits_total", assistant.STATS["cache_hits"]),
            _line("hiring_assistant_refused_total", assistant.STATS["refused"])]
    return "\n".join(out) + "\n"
