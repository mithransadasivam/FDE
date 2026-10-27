"""A trace per agent run: spans are kept in the database (Trust & cost tab) and, when PHOENIX_ENDPOINT is set, exported to Phoenix."""
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar

from app.config import get_settings
from app.db import OpsSession
from app.models_ext import AgentTrace

_current_trace: ContextVar[str | None] = ContextVar("trace_id", default=None)
_otel = None
_otel_tried = False


def _otel_tracer():
    """OpenTelemetry tracer that exports to Phoenix, or None when no endpoint is configured."""
    global _otel, _otel_tried
    if _otel_tried:
        return _otel
    _otel_tried = True
    endpoint = get_settings().phoenix_endpoint
    if not endpoint:
        return None
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": "hiring-intelligence", "openinference.project.name": "hiring-intelligence"}))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
        _otel = trace.get_tracer("hiring-intelligence")
    except Exception:
        _otel = None
    return _otel


@contextmanager
def trace_run(name: str):
    """Groups the spans of one run (for example one candidate's journey step) under one trace id."""
    token = _current_trace.set(uuid.uuid4().hex[:16])
    try:
        yield _current_trace.get()
    finally:
        _current_trace.reset(token)


@contextmanager
def span(agent: str, name: str, candidate_id: int | None = None, **attrs):
    """Times one step of an agent and records it. Errors are recorded and re-raised."""
    start = time.perf_counter()
    status = "ok"
    otel = _otel_tracer()
    cm = otel.start_as_current_span(f"{agent}.{name}") if otel else None
    otel_span = cm.__enter__() if cm else None
    try:
        yield
    except Exception as e:
        status = f"error: {type(e).__name__}"
        raise
    finally:
        ms = (time.perf_counter() - start) * 1000
        if otel_span is not None:
            otel_span.set_attribute("openinference.span.kind", "AGENT")
            otel_span.set_attribute("agent.name", agent)
            if candidate_id is not None:
                otel_span.set_attribute("candidate.id", candidate_id)
            cm.__exit__(None, None, None)
        try:
            with OpsSession() as db:
                db.add(AgentTrace(trace_id=_current_trace.get() or uuid.uuid4().hex[:16], agent=agent, name=name, candidate_id=candidate_id,
                                  duration_ms=round(ms, 3), status=status, attrs=attrs or None))
                db.commit()
        except Exception:
            pass
