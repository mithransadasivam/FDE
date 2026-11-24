"""Day 10: the console's side of the case workflows (done, not a ticket).

The console's API never runs a workflow itself. It starts one (on the worker's queue), sends it messages (a person's decision,
a document from the applicant), and reads its progress from the DBOS database. So the console can restart as often as it
likes: the workflows live in the worker and in the database.
"""

import csv
import json
import time

import httpx

from app import store
from app.agent import runs
from app.agent.models import Approval
from app.config import BANK_URL, DAY_SECONDS, QUEUE_EXPECTED_FILE_10, WEBHOOK_SECRET
from app.integration.models import WebhookRejected
from app.integration.webhooks import verify_webhook
from app.workflow import engine, grants, steps
from app.workflow.chase import DOCUMENTS

ENDS = {"completed", "escalated", "stopped", "handed_back", "rejected", "expired", "recorded", "error"}


class WorkerNotReady(Exception):
    pass


def _cases() -> dict:
    return store.load("workflow/cases.json", {})


def _bank(path: str, **params) -> dict:
    try:
        r = httpx.get(f"{BANK_URL}{path}", params=params, timeout=10)
        return r.json() if r.status_code == 200 else {}
    except httpx.HTTPError:
        return {}


def worker() -> dict:
    s = engine._read(engine.WORKFLOW_DIR / "worker.json", {})
    alive = bool(s.get("heartbeat")) and time.time() - s["heartbeat"] < 4
    crashes = engine._read(engine.CRASH_LOG, [])
    return {"up": alive, "pid": s.get("pid"), "started_at": s.get("started_at"), "starts": len(s.get("starts", [])),
            "crashes": crashes[::-1][:20], "armed": engine._read(engine.CRASH_FILE, []), "day_seconds": DAY_SECONDS,
            "points": engine.crash_points()}


def _client():
    if not engine.WORKFLOW_DB.exists():
        raise WorkerNotReady("The workflow worker has not started yet: run npm run dev (it starts python -m app.workflow.worker)")
    return engine.client()


# ---------------------------------------------------------------- starting a case
def start_case(token: str, ticket_id: str, prompt: str = "") -> str:
    from app.config import WORKFLOW_PROMPT

    ident = runs.identity_for(token)
    c = _client()
    with runs._lock:
        cases = _cases()
        n = 1 + sum(1 for k in cases if k.startswith(f"case-{ticket_id}-"))
        key = f"case-{ticket_id}-{n}"
        cases[key] = {"key": key, "ticket_id": ticket_id, "person": ident.sub, "prompt": prompt or WORKFLOW_PROMPT, "started_at": time.time()}
        store.save("workflow/cases.json", cases)
    grants.open_grant(ident, ticket_id, key)
    steps.note(key, "start", f"{ident.sub} started the case workflow for {ticket_id}, and delegated the case to it")
    c.enqueue({"queue_name": engine.QUEUE, "workflow_name": "work_case", "workflow_id": key, "app_version": engine.APP_VERSION},
              ticket_id, prompt or WORKFLOW_PROMPT)
    return key


def active_case(ticket_id: str) -> str | None:
    """The newest workflow for this exception that has not ended."""
    keys = sorted((k for k, v in _cases().items() if v["ticket_id"] == ticket_id), key=lambda k: _cases()[k]["started_at"])
    for k in reversed(keys):
        if not any(e["kind"] == "end" for e in steps.events(k)):
            return k
    return None


# ---------------------------------------------------------------- reading a case
def _status_of(keys: list[str]) -> dict:
    try:
        return {w.workflow_id: w for w in _client().list_workflows(workflow_ids=keys, load_input=False)} if keys else {}
    except WorkerNotReady:
        return {}


def _end(ev: list[dict]) -> str:
    return next((e.get("end", "") for e in reversed(ev) if e["kind"] == "end"), "")


def summary(key: str, rec: dict, wf=None) -> dict:
    ev = steps.events(key)
    t0 = rec["started_at"]
    pending = [a for a in runs.approvals() if a.get("workflow_id") == key and a["status"] == "pending"]
    end = _end(ev)
    state = end or ("waiting_approval" if pending else next(
        (k for k in ("escalate", "send_reminder", "send_request", "documents", "apply", "propose") if ev and ev[-1]["kind"].startswith(k)), "running"))
    if not end and ev and ev[-1]["kind"] in ("sent", "replayed"):
        state = "waiting_documents"
    if not end and wf is not None and wf.status == "ERROR":
        state = "error"
    return {"key": key, "ticket_id": rec["ticket_id"], "person": rec["person"], "started_at": t0, "state": state, "end": end,
            "day": engine.course_day(t0, (ev[-1]["at"] if end else time.time())), "last": ev[-1]["text"] if ev else "",
            "dbos_status": wf.status if wf is not None else "", "recovered": max(0, (wf.recovery_attempts or 1) - 1) if wf is not None else 0,
            "approvals": len(pending)}


def list_cases(person: str | None = None) -> list[dict]:
    cases = {k: v for k, v in _cases().items() if not person or v["person"] == person}
    st = _status_of(list(cases))
    rows = [summary(k, v, st.get(k)) for k, v in cases.items()]
    return sorted(rows, key=lambda r: r["started_at"], reverse=True)


def effects(ticket_id: str, since: float = 0) -> dict:
    """What the bank's systems hold for this exception: messages to the applicant, CaseFlow outcomes, comments."""
    t = next((x for x in _bank("/course/contact-log").get("messages", []) if x["ticket_id"] == ticket_id), None)
    msgs = [m for m in _bank("/course/contact-log", ticket_id=ticket_id).get("messages", []) if m["t"] >= since - 1][::-1]
    case_id = t["case_id"] if t else _case_id(ticket_id)
    outcomes = [o for o in _bank("/course/caseflow-log", limit=500).get("outcomes", []) if o["case_ref"] == case_id][::-1]
    since_s = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(since - 1)) if since else ""
    outcomes = [o for o in outcomes if o["at"] >= since_s]
    comments = [c for c in _bank("/course/exception-comments", ticket_id=ticket_id).get("comments", []) if c["at"] >= since_s[:16]]
    return {"case_id": case_id, "messages": msgs, "outcomes": outcomes, "comments": comments}


def counts(eff: dict) -> dict:
    """The writes the bank holds for one case: what the exactly-once checks count."""
    return {"requests": sum(m["kind"] == "request" for m in eff["messages"]), "reminders": sum(m["kind"] == "reminder" for m in eff["messages"]),
            "caseflow_outcomes": len(eff["outcomes"]), "outcome_comments": sum(c["text"].startswith("Outcome recorded") for c in eff["comments"]),
            "escalations": sum(c["text"].startswith("Escalated to") for c in eff["comments"])}


def _case_id(ticket_id: str) -> str:
    from app.config import DATA_DIR

    t = json.loads((DATA_DIR / "Day08_Slide10_kyc_exceptions.json").read_text())["tickets"]
    return next((x["case_id"] for x in t if x["ticket_id"] == ticket_id), "")


def case_detail(key: str) -> dict | None:
    rec = _cases().get(key)
    if not rec:
        return None
    st = _status_of([key])
    wf = st.get(key)
    t0 = rec["started_at"]
    try:
        dsteps = _client().list_workflow_steps(key) if wf is not None else []
    except WorkerNotReady:
        dsteps = []
    ev = [{**e, "day": engine.course_day(t0, e["at"])} for e in steps.events(key)]
    agent_runs = [r for r in runs.list_runs(500) if r["id"].startswith(key + "-")]
    eff = effects(rec["ticket_id"], t0)
    for m in eff["messages"]:
        m["day"] = engine.course_day(t0, m["t"])
    return {**summary(key, rec, wf), "events": ev, "counts": counts(eff),
            "steps": [{"n": s["function_id"], "name": s["function_name"], "error": str(s["error"]) if s["error"] else "",
                       "day": engine.course_day(t0, s["started_at_epoch_ms"] / 1000) if s.get("started_at_epoch_ms") else None,
                       "done_day": engine.course_day(t0, s["completed_at_epoch_ms"] / 1000) if s.get("completed_at_epoch_ms") else None}
                      for s in dsteps],
            "approvals": [a for a in runs.approvals() if a.get("workflow_id") == key],
            "runs": sorted(agent_runs, key=lambda r: r["started_at"]), "effects": eff,
            "tokens_in": sum(r["tokens_in"] for r in agent_runs), "cost_usd": round(sum(r.get("cost_usd") or 0 for r in agent_runs), 6)}


# ---------------------------------------------------------------- messages to workflows
def decide(approval_id: str, approve: bool, person: str, note: str = "") -> dict:
    """The person's decision: saved with the approval (Day 9), and sent to the workflow that waits for it."""
    a = runs.decide(approval_id, approve, person, note)
    if a.get("workflow_id"):
        _client().send(a["workflow_id"], {"approval_id": a["id"], "status": a["status"], "decided_by": person, "note": note}, a["id"])
        steps.note(a["workflow_id"], "decided", f"{person} {a['status']} the proposal" + (f": {note}" if note else ""))
    return a


def receive_document(headers: dict, body: bytes) -> dict:
    """The document store's webhook: checked like every webhook (ENG-803), then passed to the workflow chasing that applicant."""
    seen = set(store.load("workflow/doc_seen.json", []))
    log = store.load("workflow/doc_log.json", [])
    try:
        event = verify_webhook(headers, body, WEBHOOK_SECRET, time.time(), seen)
    except WebhookRejected as e:
        log.append({"at": time.time(), "outcome": "refused", "reason": str(e)})
        store.save("workflow/doc_log.json", log[-200:])
        raise
    store.save("workflow/doc_seen.json", sorted(seen)[-1000:])
    data = event["data"]
    key = active_case(data["ticket_id"]) if event.get("type") == "document.received" else None
    if key:
        _client().send(key, data, DOCUMENTS)
    log.append({"at": time.time(), "outcome": "accepted", "event_id": event["id"], "ticket_id": data.get("ticket_id"), "to": key})
    store.save("workflow/doc_log.json", log[-200:])
    return {"received": event["id"], "workflow": key}


# ---------------------------------------------------------------- course controls
def crash(point: str, ticket: str = "*") -> dict:
    engine.arm(point, ticket)
    return worker()


def applicant_reply(ticket_id: str, doc_type: str) -> dict:
    r = httpx.post(f"{BANK_URL}/course/applicant-reply", json={"ticket_id": ticket_id, "doc_type": doc_type}, timeout=20)
    return r.json()


# ---------------------------------------------------------------- Tom's queue (Activity 4)
def expected_queue() -> dict:
    with open(QUEUE_EXPECTED_FILE_10, newline="", encoding="utf-8") as f:
        return {r["ticket_id"]: r for r in csv.DictReader(f)}


def start_queue(token: str, tickets: list[str]) -> dict:
    keys = [start_case(token, t) for t in tickets]
    store.save("workflow/queue.json", {"keys": keys, "started_at": time.time()})
    return {"keys": keys}


def queue_state() -> dict | None:
    q = store.load("workflow/queue.json", None)
    if not q:
        return None
    exp = expected_queue()
    cases = _cases()
    st = _status_of(q["keys"])
    rows = []
    for k in q["keys"]:
        rec = cases.get(k)
        if not rec:
            continue
        s = summary(k, rec, st.get(k))
        e = exp.get(rec["ticket_id"], {})
        got = counts(effects(rec["ticket_id"], rec["started_at"]))
        ok = bool(e) and s["end"] == e["expected_end"] and all(int(e[f]) == got[f] for f in ("requests", "reminders", "escalations", "caseflow_outcomes"))
        rows.append({**s, **got, "expected": e, "ok": ok, "done": bool(s["end"])})
    return {"rows": rows, "ok": sum(r["ok"] for r in rows), "total": len(exp), "done": all(r["done"] for r in rows) and bool(rows),
            "started_at": q["started_at"]}
