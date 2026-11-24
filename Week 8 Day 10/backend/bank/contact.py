"""The bank's applicant contact gateway (Day 10, done): every message the bank sends an applicant goes through it.

A message to an applicant is a regulated communication: the gateway keeps each one, in the name of the person it is sent for,
and honours an Idempotency-Key header. The same key twice returns the first message and sends nothing new; the same key with
a different message is refused. A request without the header is always sent.

Course stand-ins (not part of a real bank):
  - the applicants: when a request reaches an applicant listed in data/Day10_Slide26_applicant_replies.json, they reply
    on schedule, in course days (FDE_DAY_SECONDS): a document arrives in the document store, CaseFlow Classic notes it,
    and the document store calls the console's webhook (document.received), signed like every other webhook
  - POST /course/applicant-reply makes any applicant reply now
"""

import hashlib
import json
import os
import threading
import time
import uuid

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse

from bank import core, legacy, systems

router = APIRouter()
course = APIRouter()
KINDS = {"request": "Request for documents", "reminder": "Reminder"}
DOC_NAMES = {"passport": "passport", "driving_licence": "driving licence", "utility_bill": "utility bill",
             "bank_statement": "bank statement", "council_tax_bill": "council tax bill"}


def messages() -> list[dict]:
    return core.load("contact.json", [])


def _scenario() -> dict:
    p = core.DATA / "Day10_Slide26_applicant_replies.json"
    return json.loads(p.read_text(encoding="utf-8"))["replies"] if p.exists() else {}


def _digest(body: dict) -> str:
    return hashlib.sha256(json.dumps({k: body.get(k) for k in ("ticket_id", "kind", "text")}, sort_keys=True).encode()).hexdigest()


@router.post("/contact/messages")
def send(request: Request, body: dict = Body(...)):
    claims = systems._claims(request, "contact")
    tid = str(body.get("ticket_id", ""))
    systems._need_scope(claims, "kyc.write", "contact", "send to applicant", tid)
    t = systems._visible_ticket(claims, tid, "send to applicant")
    kind, text = body.get("kind"), str(body.get("text", ""))
    if kind not in KINDS or not text or len(text) > 600:
        raise HTTPException(422, "A message needs a kind (request or reminder) and a text of at most 600 characters")
    key = request.headers.get("idempotency-key", "")
    with core._lock:
        log = messages()
        if key:
            first = next((m for m in log if m.get("key") == key), None)
            if first:
                if first["digest"] != _digest(body):
                    core.audit("contact", claims, f"send {kind}", tid, "refused", "Idempotency-Key reused for a different message")
                    raise HTTPException(422, "This Idempotency-Key was used for a different message")
                core.audit("contact", claims, f"send {kind}", tid, "allowed", f"replayed {first['id']}: nothing sent")
                return JSONResponse({**first, "replayed": True}, headers={"Idempotent-Replayed": "true"})
        act = claims.get("act") or {}
        m = {"id": f"MSG-{5001 + len(log)}", "ticket_id": tid, "case_id": t["case_id"], "customer_id": t["customer_id"], "kind": kind,
             "text": text, "by": claims["sub"], "via": act.get("sub"), "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "t": time.time(),
             "key": key or None, "digest": _digest(body)}
        log.append(m)
        core.save("contact.json", log)
    core.audit("contact", claims, f"send {kind}", tid, "allowed", m["id"])
    if kind == "request":
        _schedule_reply(tid)
    return {**m, "replayed": False}


# ---------------------------------------------------------------- the applicants (course stand-in)
def _schedule_reply(tid: str) -> None:
    plan = _scenario().get(tid)
    if not plan:
        return
    with core._lock:
        sched = core.load("applicant_schedule.json", {})
        if tid in sched:  # a second request (sent twice) does not make the applicant reply twice
            return
        sched[tid] = {"due": time.time() + float(plan["after_days"]) * core.DAY_SECONDS, "doc_type": plan["doc_type"], "done": False}
        core.save("applicant_schedule.json", sched)


def reply(tid: str, doc_type: str) -> dict:
    """The applicant sends a document: it lands in the document store, CaseFlow notes it, and the console hears of it."""
    t = next((x for x in systems.tickets() if x["ticket_id"] == tid), None)
    if not t:
        raise HTTPException(404, f"No exception {tid}")
    if doc_type not in DOC_NAMES:
        raise HTTPException(422, f"Unknown document type {doc_type}")
    with core._lock:
        added = core.load("docs_added.json", [])
        doc = {"doc_id": f"D-9{len(added) + 1:04d}", "customer_id": t["customer_id"], "team_id": t["team_id"], "doc_type": doc_type,
               "received_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "pages": 1, "source": "applicant upload"}
        added.append(doc)
        core.save("docs_added.json", added)
    today = time.strftime("%d/%m/%Y")
    name = DOC_NAMES[doc_type]
    legacy.add_history(t["case_id"], {"date": today, "by": "SYSTEM", "entry": f"Applicant replied to our request (web upload): sent a {name}."})
    legacy.add_history(t["case_id"], {"date": today, "by": "SYSTEM", "entry": f"Document received: {name} ({doc['doc_id']})."})
    ev = {"id": "evt_" + uuid.uuid4().hex[:16], "type": "document.received", "created": int(time.time()),
          "data": {"ticket_id": tid, "case_id": t["case_id"], "customer_id": t["customer_id"], "team_id": t["team_id"],
                   "doc_id": doc["doc_id"], "doc_type": doc_type}}
    url = os.getenv("FDE_DOCS_WEBHOOK_URL", "http://localhost:8000/api/hooks/documents")
    delivery = systems.deliver(ev, url=url)
    return {"document": doc, "event": ev, "delivery": delivery}


def _applicants_loop() -> None:
    while True:
        time.sleep(0.25)
        try:
            sched = core.load("applicant_schedule.json", {})
            for tid, s in sched.items():
                if not s["done"] and time.time() >= s["due"]:
                    with core._lock:
                        cur = core.load("applicant_schedule.json", {})
                        cur[tid]["done"] = True
                        core.save("applicant_schedule.json", cur)
                    reply(tid, s["doc_type"])
        except Exception:  # a course stand-in: never take the bank's server down
            pass


def start_applicants() -> None:
    threading.Thread(target=_applicants_loop, daemon=True, name="applicants").start()


@course.get("/course/contact-log")
def contact_log(ticket_id: str = ""):
    rows = [{k: v for k, v in m.items() if k != "digest"} for m in messages() if not ticket_id or m["ticket_id"] == ticket_id]
    return {"messages": rows[::-1], "scheduled": core.load("applicant_schedule.json", {}), "day_seconds": core.DAY_SECONDS}


@course.post("/course/applicant-reply")
def applicant_reply(body: dict = Body(...)):
    return reply(str(body.get("ticket_id", "")), str(body.get("doc_type", "utility_bill")))
