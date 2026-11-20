"""Day 9 API: the Agent runs screen (/api/agent/…). The agent acts for the person signed in to the console."""

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

import threading

from app.agent import evaluate as agent_eval
from app.agent import runs
from app.agent.approvals import gate
from app.agent.limits import check_limits
from app.agent.models import ScreenError
from app.agent.screen import find_element
from app.config import BANK_URL, LEGACY_URL
from app.integration import auth, tools
from app.integration.models import ToolRefused
from app.llm import settings

router = APIRouter(prefix="/api/agent")


def _session(request: Request) -> dict:
    s = auth.session(request.cookies.get(auth.COOKIE))
    if not s:
        raise HTTPException(401, "Sign in with the bank first: the agent acts as the person signed in")
    return s


def _bank(path: str):
    try:
        r = httpx.get(f"{BANK_URL}{path}", timeout=10)
        return r.json() if r.status_code == 200 else None
    except httpx.HTTPError:
        return None


@router.get("/status")
def status(request: Request):
    s = auth.session(request.cookies.get(auth.COOKIE))
    return {"person": s["person"] if s else None, "legacy_url": LEGACY_URL, "legacy_up": _bank("/health") is not None,
            "fake": settings()["fake"], "model": runs.new_run("x", "x").model, "prompts": runs.prompts(), "limits": runs.limits(),
            "rules": runs.rules(), "tickets": tickets_built()}


def tickets_built() -> dict:
    """Which of today's tickets are built, judged by what each function does (shown on the Agent runs screen)."""
    out = {}
    els = [{"role": "button", "name": n, "ref": f"e{i}"} for i, n in enumerate(["Back", "Withdraw case", "Confirm"], 1)]
    try:
        out["ENG-901"] = find_element(els, "button", "Confirm")["name"] == "Confirm"
    except ScreenError:
        out["ENG-901"] = False
    try:
        out["ENG-902"] = check_limits([{"tool": "look", "args": {}}] * 30, {"tool": "look", "args": {}}, runs.limits(), 0, 0) is not None
    except NotImplementedError:
        out["ENG-902"] = False
    d = gate({"system": "caseflow", "tool": "click", "target": "Confirm", "fingerprint": "probe"}, runs.rules(), [], 0)
    out["ENG-903"] = d.kind == "ask"
    return out


@router.get("/exceptions")
def my_exceptions(request: Request):
    s = _session(request)
    try:
        ident = runs.identity_for(s["token"])
        found = tools.list_exceptions(ident)["tickets"]
    except ToolRefused as e:
        raise HTTPException(403, str(e))
    last = {}
    for r in runs.list_runs(200):
        last.setdefault(r["ticket_id"], r)
    return {"person": s["person"]["sub"], "tickets": [t | {"last_run": last.get(t["ticket_id"])} for t in found if t["status"] != "resolved"]}


class RunIn(BaseModel):
    ticket_id: str
    prompt: str = "ops_v1"


@router.post("/runs")
def start(body: RunIn, request: Request):
    s = _session(request)
    if body.prompt not in runs.prompts():
        raise HTTPException(400, f"No prompt {body.prompt}")
    return {"run_id": runs.start_run(body.ticket_id, s["token"], body.prompt)}


@router.get("/runs")
def list_runs():
    return {"runs": runs.list_runs()}


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    r = runs.get_run(run_id)
    if not r:
        raise HTTPException(404, f"No run {run_id}")
    return r


@router.get("/runs/{run_id}/shots/{name}")
def shot(run_id: str, name: str):
    p = runs.shot_path(run_id, name)
    if "/" in name or ".." in name or not p.exists():
        raise HTTPException(404, "No such screenshot")
    return FileResponse(p, media_type="image/png")


@router.get("/approvals")
def approvals():
    rows = runs.approvals()
    return {"pending": [a for a in rows if a["status"] == "pending"], "recent": [a for a in rows if a["status"] != "pending"][-20:][::-1]}


class DecideIn(BaseModel):
    decision: str  # approve | reject
    note: str = ""


@router.post("/approvals/{approval_id}")
def decide(approval_id: str, body: DecideIn, request: Request):
    s = _session(request)
    try:
        return runs.decide(approval_id, body.decision == "approve", s["person"]["sub"], body.note)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.post("/queue")
def queue(request: Request):
    s = _session(request)
    sid = request.cookies.get(auth.COOKIE)
    ident = runs.identity_for(s["token"])
    tickets = [t["ticket_id"] for t in tools.list_exceptions(ident)["tickets"] if t["status"] != "resolved"]
    return {"queue_id": runs.start_queue(lambda: auth.session(sid)["token"], tickets)}


@router.get("/queue")
def queue_state():
    return {"queue": runs.queue_state()}


@router.get("/caseflow")
def caseflow():
    log = _bank("/course/caseflow-log") or {"outcomes": [], "cases": {}}
    audit = (_bank("/audit?system=caseflow&limit=30") or {"entries": []})["entries"]
    return {**log, "audit": audit, "url": LEGACY_URL}


# ---------------------------------------------------------------- homework: the 20 evaluation cases, in shadow mode
_eval_state: dict = {"running": None, "log": [], "error": ""}


class EvalIn(BaseModel):
    prompt: str = "ops_v1"


@router.get("/evals")
def evals():
    spec = agent_eval.cases()
    return {"cases": spec["cases"], "run_as": spec["run_as"], "saved": agent_eval.saved(), "running": _eval_state["running"],
            "log": _eval_state["log"][-25:], "error": _eval_state["error"], "gate_built": agent_eval.gate_is_built()}


@router.post("/evals")
def run_evals(body: EvalIn):
    if _eval_state["running"]:
        raise HTTPException(409, f"An evaluation of {_eval_state['running']} is already running")
    if body.prompt not in runs.prompts():
        raise HTTPException(400, f"No prompt {body.prompt}")
    if not agent_eval.gate_is_built():
        raise HTTPException(409, "Build ENG-903 first: shadow mode relies on the gate asking before Confirm")

    def work():
        _eval_state.update(running=body.prompt, log=[], error="")
        try:
            agent_eval.evaluate(body.prompt, progress=_eval_state["log"].append)
        except Exception as e:
            _eval_state["error"] = f"{type(e).__name__}: {e}"
        finally:
            _eval_state["running"] = None

    threading.Thread(target=work, daemon=True).start()
    return {"started": body.prompt}
