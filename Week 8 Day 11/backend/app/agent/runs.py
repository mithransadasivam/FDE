"""Day 9: starting runs, keeping them, and the approvals people give (done, not a ticket).

A run works in a background thread of the console's API, as the person signed in to the console. When the gate asks,
the run waits (up to FDE_APPROVAL_WAIT_S) for that person to approve or reject on the Agent runs screen.
Runs are saved in engagement/agent/runs/<id>.json, with one screenshot per screen step beside them.
"""

import csv
import json
import threading
import time
import uuid

import httpx

from app import store
from app.agent import actions, loop
from app.agent.models import Approval, Run
from app.config import (ACTION_RISKS_FILE_9, AGENT_PROMPTS_DIR, APPROVAL_WAIT_S, BANK_ISSUER, BANK_URL, LEGACY_URL, MCP_RESOURCE,
                        PLAYBOOK_FILE_9, QUEUE_EXPECTED_FILE_9, RUN_LIMITS_FILE_9)
from app.integration.models import Identity
from app.integration.tokens import verify_access_token
from app.llm import llm_client, settings
from app.pipeline.service import CLASS_MODEL, usd

_lock = threading.RLock()
_waiting: dict[str, threading.Event] = {}
_jwks: dict = {"at": 0, "keys": None}


def limits() -> dict:
    return json.loads(RUN_LIMITS_FILE_9.read_text(encoding="utf-8"))


def rules() -> list[dict]:
    with open(ACTION_RISKS_FILE_9, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def prompts() -> list[str]:
    return sorted(p.stem for p in AGENT_PROMPTS_DIR.glob("ops_v*.md"))


def prompt_text(name: str) -> str:
    return (AGENT_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def identity_for(token: str) -> Identity:
    """The person behind the console's session token, checked as the MCP server checks it (ENG-801)."""
    if _jwks["keys"] is None or time.time() - _jwks["at"] > 300:
        _jwks["keys"] = httpx.get(f"{BANK_URL}/jwks.json", timeout=10).json()
        _jwks["at"] = time.time()
    return verify_access_token(token, _jwks["keys"], BANK_ISSUER, MCP_RESOURCE, ["kyc.read"])


# ---------------------------------------------------------------- storage
def _run_name(run_id: str) -> str:
    return f"agent/runs/{run_id}.json"


def save_run(run: Run) -> None:
    run.cost_usd = usd(run.tokens_in, run.tokens_out, run.model or CLASS_MODEL)
    with _lock:
        store.save(_run_name(run.id), run.model_dump())


def get_run(run_id: str) -> dict | None:
    return store.load(_run_name(run_id), None)


def list_runs(limit: int = 50) -> list[dict]:
    d = store.path("agent/runs")
    files = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit] if d.exists() else []
    out = []
    for p in files:
        r = json.loads(p.read_text(encoding="utf-8"))
        out.append({k: r[k] for k in ("id", "ticket_id", "person", "prompt", "mode", "status", "stop_reason", "outcome", "reference",
                                      "started_at", "ended_at", "tokens_in", "tokens_out", "cost_usd", "queue_id")} | {"steps": len(r["steps"])})
    return out


def shot_path(run_id: str, name: str):
    return store.path(f"agent/runs/{run_id}") / name


def approvals() -> list[dict]:
    return store.load("agent/approvals.json", [])


def _save_approval(a: Approval) -> None:
    with _lock, store.locked("agent/approvals.json"):
        rows = [x for x in approvals() if x["id"] != a.id] + [a.model_dump()]
        store.save("agent/approvals.json", rows[-300:])


def decide(approval_id: str, approve: bool, person: str, note: str = "") -> dict:
    with _lock, store.locked("agent/approvals.json.decide"):
        a = next((x for x in approvals() if x["id"] == approval_id), None)
        if not a:
            raise KeyError(f"No approval {approval_id}")
        if a["status"] != "pending":
            raise ValueError(f"Approval {approval_id} is already {a['status']}")
        if person != a["person"]:
            raise PermissionError(f"Only {a['person']} can decide this approval: the agent acts for them")
        a.update(status="approved" if approve else "rejected", decided_by=person, note=note, decided_at=time.time())
        _save_approval(Approval(**a))
    ev = _waiting.get(approval_id)
    if ev:
        ev.set()
    return a


def _wait_for_person(ap: Approval) -> Approval:
    ev = threading.Event()
    _waiting[ap.id] = ev
    _save_approval(ap)
    ev.wait(APPROVAL_WAIT_S)
    _waiting.pop(ap.id, None)
    a = next(x for x in approvals() if x["id"] == ap.id)
    if a["status"] == "pending":
        a.update(status="expired", decided_by="nobody", note=f"No one decided within {APPROVAL_WAIT_S} s", decided_at=time.time())
        _save_approval(Approval(**a))
    return Approval(**a)


def shadow_approver(ap: Approval) -> Approval:
    """Evaluation (homework): every approval is refused and recorded, so nothing is written to CaseFlow."""
    ap = ap.model_copy(update={"status": "rejected", "decided_by": "shadow mode", "note": "Evaluation: proposed, not written",
                               "decided_at": time.time()})
    _save_approval(ap)
    return ap


# ---------------------------------------------------------------- runs
def new_run(ticket_id: str, person: str, prompt: str = "ops_v1", mode: str = "live", queue_id: str = "") -> Run:
    s = settings()
    return Run(id=time.strftime("%m%d-%H%M%S-") + uuid.uuid4().hex[:4], ticket_id=ticket_id, person=person, prompt=prompt,
               model=CLASS_MODEL if s["fake"] else s["openrouter_model"], mode=mode, queue_id=queue_id, started_at=time.time())


def execute_run(run: Run, identity: Identity, approver=None, client=None) -> Run:
    ctx = actions.RunContext(identity=identity, legacy_url=LEGACY_URL, shots_dir=store.path(f"agent/runs/{run.id}"), run=run)
    save_run(run)
    return loop.run_agent(ctx, client or llm_client(), prompt_text(run.prompt), PLAYBOOK_FILE_9.read_text(encoding="utf-8"),
                          limits(), rules(), approver or _wait_for_person, save_run)


def start_run(ticket_id: str, token: str, prompt: str = "ops_v1") -> str:
    ident = identity_for(token)
    run = new_run(ticket_id, ident.sub, prompt)
    save_run(run)
    threading.Thread(target=execute_run, args=(run, ident), daemon=True, name=f"agent-{run.id}").start()
    return run.id


# ---------------------------------------------------------------- the queue (Activity 4)
def expected_queue() -> dict:
    with open(QUEUE_EXPECTED_FILE_9, newline="", encoding="utf-8") as f:
        return {r["ticket_id"]: r for r in csv.DictReader(f)}


def scorecard(run_rows: list[dict]) -> dict:
    exp = expected_queue()
    rows = []
    for r in run_rows:
        e = exp.get(r["ticket_id"])
        if not e:
            continue
        ok = r["status"] == e["expected_end"] and (not e["expected_outcome"] or r["outcome"] == e["expected_outcome"])
        rows.append({"ticket_id": r["ticket_id"], "run_id": r["id"], "status": r["status"], "outcome": r["outcome"],
                     "reference": r.get("reference", ""), "stop_reason": r.get("stop_reason", ""), "steps": r.get("steps", 0),
                     "expected_end": e["expected_end"], "expected_outcome": e["expected_outcome"], "why": e["why"], "ok": ok})
    return {"rows": rows, "ok": sum(r["ok"] for r in rows), "total": len(exp)}


def queue_state() -> dict | None:
    q = store.load("agent/queue.json", None)
    if not q:
        return None
    runs = [get_run(i) for i in q["runs"]]
    runs = [r | {"steps": len(r["steps"])} for r in runs if r]
    done = q["status"] == "done"
    return {**q, "runs": runs, "scorecard": scorecard(runs) if done else None,
            "cost_usd": round(sum(r.get("cost_usd") or 0 for r in runs), 6)}


def start_queue(get_token, ticket_ids: list[str], prompt: str = "ops_v1") -> str:
    """get_token() gives the person's current token (the console refreshes it), so a long queue keeps working."""
    ident = identity_for(get_token())
    qid = "q-" + uuid.uuid4().hex[:6]
    store.save("agent/queue.json", {"id": qid, "person": ident.sub, "tickets": ticket_ids, "runs": [], "status": "running",
                                    "started_at": time.time()})

    def work():
        for t in ticket_ids:
            run = new_run(t, ident.sub, prompt, queue_id=qid)
            q = store.load("agent/queue.json", {})
            q["runs"].append(run.id)
            store.save("agent/queue.json", q)
            execute_run(run, identity_for(get_token()))
        q = store.load("agent/queue.json", {})
        q.update(status="done", ended_at=time.time())
        store.save("agent/queue.json", q)

    threading.Thread(target=work, daemon=True, name=f"queue-{qid}").start()
    return qid
