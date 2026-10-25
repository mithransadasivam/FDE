"""FastAPI service: /triage, /incidents, /ask, /health, /ready, /metrics, plus approvals, the crew stream, replay and the status page.

Start it:  uvicorn tower.api:create_app --factory --port 8000
"""
from __future__ import annotations

import json
import time
from typing import Iterator

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from . import __version__
from .actions import ActionError, actions_log_lines
from .crew import ROSTER
from .evaluate import score
from .guardrails import presidio_ready
from .models import ActionRequest, ApprovalIn, AskIn, TriageIn
from .observability import new_request_id, request_id_var, setup_logging, get_logger
from .settings import Settings
from .tower import Tower


def create_app(tower: Tower | None = None) -> FastAPI:
    s = tower.s if tower else Settings.from_env()
    setup_logging(s.app_log)
    t = tower or Tower(s)
    log = get_logger()
    app = FastAPI(title="Operations Control Tower", version=__version__,
                  description="Alerts in, incidents grouped by rules, a crew of agents, and a person approves every change.")
    app.state.tower = t

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id") or new_request_id()
        token = request_id_var.set(rid)
        t0 = time.perf_counter()
        status, err = 500, True
        try:
            with t.tracer.span("http", path=request.url.path, method=request.method):
                response = await call_next(request)
            status, err = response.status_code, response.status_code >= 500
            response.headers["x-request-id"] = rid
            return response
        finally:
            ms = (time.perf_counter() - t0) * 1000
            path = request.url.path
            if path.startswith("/incidents/") and "/crew" in path:
                path = "/incidents/{id}/crew"
            elif path.startswith("/incidents/"):
                path = "/incidents/{id}"
            elif path.startswith("/actions/"):
                path = "/actions/{id}"
            t.metrics.request(path, ms, err)
            if path not in ("/metrics", "/health"):
                log.info(f"{request.method} {path} {status}", extra={"event": "request", "route": path, "ms": round(ms, 1), "status": status})
            request_id_var.reset(token)

    def _err(e: ActionError):
        raise HTTPException(status_code=e.code, detail=str(e))

    # ---- core ----
    @app.post("/triage")
    def post_triage(body: TriageIn):
        incs = t.triage(body.alerts or None, with_brief=body.with_brief)
        return {"count": len(incs), "alerts": sum(len(i.alert_ids) for i in incs), "incidents": [i.model_dump() for i in incs]}

    @app.get("/incidents")
    def get_incidents():
        return [i.model_dump(exclude={"crew", "brief"}) | {"has_brief": i.brief is not None} for i in t.list_incidents()]

    @app.get("/incidents/{incident_id}")
    def get_incident(incident_id: str):
        inc = t.get_incident(incident_id)
        if inc is None:
            raise HTTPException(404, "no such incident")
        return inc.model_dump()

    @app.post("/incidents/{incident_id}/crew")
    def run_crew(incident_id: str):
        inc = t.run_crew_on(incident_id)
        if inc is None:
            raise HTTPException(404, "no such incident")
        return inc.model_dump()

    @app.post("/incidents/{incident_id}/crew/stream")
    def crew_stream(incident_id: str):
        def gen() -> Iterator[str]:
            for ev in t.stream_crew(incident_id):
                yield json.dumps(ev, ensure_ascii=False) + "\n"
        return StreamingResponse(gen(), media_type="application/x-ndjson")

    @app.post("/ask")
    def post_ask(body: AskIn):
        return t.ask(body.question).as_dict()

    @app.post("/ask/stream")
    def post_ask_stream(body: AskIn):
        def gen() -> Iterator[str]:
            for ev in t.ask_stream(body.question):
                yield json.dumps(ev, ensure_ascii=False) + "\n"
        return StreamingResponse(gen(), media_type="application/x-ndjson")

    # ---- approvals ----
    @app.post("/actions")
    def post_action(body: ActionRequest):
        inc = t.get_incident(body.incident_id)
        if inc is None:
            raise HTTPException(404, "no such incident")
        con = t.con()
        try:
            out = t.actions.create(con, body, inc)
            con.commit()
        except ActionError as e:
            _err(e)
        finally:
            con.close()
        return out

    @app.get("/actions/{request_id}")
    def get_action(request_id: str):
        con = t.con()
        try:
            return t.actions.get(con, request_id)
        except ActionError as e:
            _err(e)
        finally:
            con.close()

    @app.post("/actions/{request_id}/decide")
    def decide(request_id: str, body: ApprovalIn):
        try:
            return t.actions.decide_safely(request_id, body)
        except ActionError as e:
            _err(e)

    @app.get("/actions-log")
    def actions_log():
        return {"lines": actions_log_lines(s.actions_log)}

    @app.get("/audit")
    def audit(limit: int = 100):
        con = t.con()
        try:
            return [dict(r) for r in con.execute("SELECT ts, actor, event, detail FROM audit ORDER BY id DESC LIMIT ?", (min(limit, 500),))]
        finally:
            con.close()

    # ---- health ----
    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__, "model_mode": s.model_mode, "presidio": presidio_ready()}

    @app.get("/ready")
    def ready(response: Response):
        r = t.ready()
        response.status_code = 200 if r["ready"] else 503
        return r

    @app.get("/metrics")
    def metrics(format: str = "json"):
        if format == "prometheus":
            return PlainTextResponse(t.metrics.prometheus())
        return t.metrics.snapshot() | {"settings": {"routing": s.routing, "cache": s.cache, "cache_ttl_s": s.cache_ttl_s,
                                                    "guardrails": s.guardrails, "approvals_enforced": s.approvals_on,
                                                    "disabled": sorted(s.disabled),
                                                    "model_mode": s.model_mode, "llm_model": t.llm.model_name("large"),
                                                    "small_model": t.llm.model_name("small"), "clock": t.clock()}}

    @app.get("/traces/recent")
    def traces(request_id: str | None = None, limit: int = 60):
        return t.tracer.recent(request_id, limit)

    @app.get("/scenarios/score")
    def scenarios_score():
        res = score(t.list_incidents())
        return {"summary": res["summary"], "rows": [{k: v for k, v in r.items() if k not in ("got", "want")} for r in res["rows"]]}

    @app.get("/crew/roster")
    def crew_roster():
        return [{"agent": k, "kind": v[0], "job": v[1]} for k, v in ROSTER.items()]

    @app.get("/reports/{name}")
    def report(name: str):
        """Saved measurement results for the Health & cost tab (perf and red-team runs). Only these names are served."""
        allowed = {"perf_fake_baseline", "perf_fake_after", "perf_real_baseline", "perf_real_after", "redteam_off", "redteam_on", "answer_check"}
        if name not in allowed:
            raise HTTPException(404, "no such report")
        p = s.root / "reports" / f"{name}.json"
        if not p.exists():
            raise HTTPException(404, "not generated yet")
        return json.loads(p.read_text(encoding="utf-8"))

    # ---- stretch: live replay, status page, escalation ----
    @app.post("/replay/reset")
    def replay_reset():
        return t.replay_reset()

    @app.post("/replay/step")
    def replay_step():
        return t.replay_step()

    @app.get("/status-page")
    def status_page():
        return t.status_page()

    @app.post("/escalations/run")
    def escalations(minutes: int = 15):
        return {"paged": t.escalate(minutes)}

    # ---- demo helpers (off unless ALLOW_ADMIN_DEBUG=1) ----
    def _need_admin():
        if not s.admin_debug:
            raise HTTPException(404, "not found")

    @app.post("/admin/model")
    def admin_model(down: bool):
        _need_admin()
        t.model_down = down
        return {"model_down": down}

    @app.post("/admin/clock")
    def admin_clock(minutes: int = 20):
        _need_admin()
        return {"clock": t.advance_clock(minutes)}

    @app.post("/admin/cache/clear")
    def admin_cache():
        _need_admin()
        t.cache.clear()
        return {"cleared": True}

    @app.post("/admin/metrics/reset")
    def admin_metrics_reset():
        _need_admin()
        t.metrics.reset()
        return {"reset": True}

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.error("unhandled error: %s", type(exc).__name__)
        return JSONResponse({"detail": "something went wrong; the request id is in the response header"}, status_code=500)

    return app
