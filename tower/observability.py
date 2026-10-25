"""Structured logs with a request id, and traces. Every log line and every span attribute is scrubbed first (policy 7.2):
secrets and personal data cannot reach a log file or a trace even if some code path forgets to hide them."""
from __future__ import annotations

import contextlib
import json
import logging
import logging.handlers
import threading
import time
import uuid
from collections import deque
from contextvars import ContextVar
from pathlib import Path

from . import guardrails

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_span_stack: ContextVar[tuple] = ContextVar("span_stack", default=())


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001
            msg = str(record.msg)
        record.msg, record.args = guardrails.scrub(msg), ()
        for k in ("detail", "question", "text"):
            if hasattr(record, k):
                setattr(record, k, guardrails.scrub(str(getattr(record, k))))
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)), "level": record.levelname,
               "request_id": request_id_var.get(), "msg": record.getMessage()}
        for k in ("event", "route", "ms", "status", "incident_id", "model", "tokens", "detail"):
            if hasattr(record, k):
                out[k] = getattr(record, k)
        return json.dumps(out, ensure_ascii=False)


_configured_path: object = "unset"


def setup_logging(path: Path | None = None) -> logging.Logger:
    """JSON lines to stderr and to a rotating file. Calling it again with another path moves the file handler."""
    global _configured_path
    log = logging.getLogger("tower")
    if _configured_path == str(path):
        return log
    for h in list(log.handlers):
        log.removeHandler(h)
        h.close()
    log.setLevel(logging.INFO)
    log.propagate = False
    flt, fmt = RedactFilter(), JsonFormatter()
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.addFilter(flt)
    log.addHandler(sh)
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(path, maxBytes=2_000_000, backupCount=2, encoding="utf-8")
        fh.setFormatter(fmt)
        fh.addFilter(flt)
        log.addHandler(fh)
    _configured_path = str(path)
    return log


def get_logger() -> logging.Logger:
    return logging.getLogger("tower")


class Tracer:
    """Spans go to an in-memory ring (shown in the Health tab) and, if configured, to Phoenix over OTLP."""

    def __init__(self, endpoint: str = "", service_name: str = "operations-control-tower"):
        self.ring: deque = deque(maxlen=600)
        self._lock = threading.Lock()
        self._otel = None
        if endpoint:
            try:
                from opentelemetry import trace
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
                from opentelemetry.sdk.resources import Resource
                from opentelemetry.sdk.trace import TracerProvider
                from opentelemetry.sdk.trace.export import BatchSpanProcessor
                provider = TracerProvider(resource=Resource.create({"service.name": service_name,
                                                                     "openinference.project.name": service_name}))
                provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces")))
                self._otel = provider.get_tracer("tower")
            except Exception as e:  # noqa: BLE001
                get_logger().warning("tracing to Phoenix is off: %s", type(e).__name__)

    @contextlib.contextmanager
    def span(self, name: str, **attrs):
        rec = {"request_id": request_id_var.get(), "name": name, "depth": len(_span_stack.get()),
               "start": time.time(), "attrs": {k: guardrails.scrub(str(v)) for k, v in attrs.items()}, "ms": 0.0, "error": ""}
        token = _span_stack.set(_span_stack.get() + (name,))
        cm = self._otel.start_as_current_span(name) if self._otel else contextlib.nullcontext()
        t0 = time.perf_counter()
        try:
            with cm as osp:
                if osp is not None:
                    osp.set_attribute("request_id", rec["request_id"])
                    for k, v in rec["attrs"].items():
                        osp.set_attribute(k, v)
                yield rec
        except BaseException as e:
            rec["error"] = type(e).__name__
            raise
        finally:
            rec["ms"] = round((time.perf_counter() - t0) * 1000, 2)
            try:
                _span_stack.reset(token)
            except ValueError:  # a streaming generator resumed in another thread's context; nothing to restore
                pass
            with self._lock:
                self.ring.append(rec)

    def recent(self, request_id: str | None = None, limit: int = 60) -> list[dict]:
        with self._lock:
            items = [r for r in self.ring if request_id is None or r["request_id"] == request_id]
        return items[-limit:]
