"""Day 10 API: the Workflows screen (/api/workflow/…) and the document store's webhook (/api/hooks/documents)."""

import inspect

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.agent import runs
from app.agent.routes import _session
from app.integration import auth, tools
from app.integration.models import ToolRefused, WebhookRejected
from app.workflow import case, chase, crashtest, service, steps, writes

router = APIRouter()


def tickets_built() -> dict:
    """Which of today's tickets are built, judged from the code (shown on the Workflows screen)."""
    wr, ch = inspect.getsource(case.work_round), inspect.getsource(chase.chase)
    body = lambda src: src.split('"""', 2)[-1]  # the code after the docstring
    k = writes.idempotency_key
    try:
        w3 = k("case-KX-1-1", 3) == k("case-KX-1-1", 3) and k("case-KX-1-1", 3) != k("case-KX-1-1", 4) and k("case-KX-1-1", 3) != k("case-KX-2-1", 3)
        rec = writes.already_recorded(["Outcome … [case-KX-1-1 r1] Reference OUT-1."], "[case-KX-1-1 r1]") and \
            not writes.already_recorded(["… [case-KX-1-1 r12] …"], "[case-KX-1-1 r1]")
    except Exception:
        w3 = rec = False
    return {"ENG-1001": "steps.propose(" in body(wr) and "DBOS.recv(" in body(wr) and "steps.apply(" in body(wr),
            "ENG-1002": "DBOS.recv(" in body(ch) and "time." not in body(ch),
            "ENG-1003": bool(w3 and rec)}


@router.get("/api/workflow/status")
def status(request: Request):
    s = auth.session(request.cookies.get(auth.COOKIE))
    return {"person": s["person"] if s else None, "worker": service.worker(), "policy": steps.load_policy(),
            "writes": steps.write_rules(), "tickets": tickets_built()}


@router.get("/api/workflow/exceptions")
def exceptions(request: Request):
    s = _session(request)
    try:
        found = tools.list_exceptions(runs.identity_for(s["token"]))["tickets"]
    except ToolRefused as e:
        raise HTTPException(403, str(e))
    return {"person": s["person"]["sub"], "tickets": [t | {"active": service.active_case(t["ticket_id"])} for t in found if t["status"] != "resolved"]}


class CaseIn(BaseModel):
    ticket_id: str
    prompt: str = ""


@router.post("/api/workflow/cases")
def start(body: CaseIn, request: Request):
    s = _session(request)
    try:
        return {"key": service.start_case(s["token"], body.ticket_id, body.prompt)}
    except service.WorkerNotReady as e:
        raise HTTPException(503, str(e))
    except ToolRefused as e:
        raise HTTPException(403, str(e))


@router.get("/api/workflow/cases")
def cases():
    return {"cases": service.list_cases()}


@router.get("/api/workflow/cases/{key}")
def case_detail(key: str):
    d = service.case_detail(key)
    if not d:
        raise HTTPException(404, f"No case workflow {key}")
    return d


class DecisionIn(BaseModel):
    approve: bool
    note: str = ""


@router.post("/api/workflow/approvals/{approval_id}")
def decide(approval_id: str, body: DecisionIn, request: Request):
    s = _session(request)
    try:
        return service.decide(approval_id, body.approve, s["person"]["sub"], body.note)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(409, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))


@router.post("/api/hooks/documents")
async def documents_hook(request: Request):
    body = await request.body()
    try:
        return await run_in_threadpool(service.receive_document, {k.lower(): v for k, v in request.headers.items()}, body)
    except WebhookRejected as e:
        raise HTTPException(400, str(e))


class CrashIn(BaseModel):
    point: str
    ticket: str = "*"


@router.post("/api/workflow/crash")
def crash(body: CrashIn):
    return service.crash(body.point, body.ticket)


class ReplyIn(BaseModel):
    ticket_id: str
    doc_type: str = "utility_bill"


@router.post("/api/workflow/applicant-reply")
def applicant_reply(body: ReplyIn):
    return service.applicant_reply(body.ticket_id, body.doc_type)


class QueueIn(BaseModel):
    tickets: list[str] = ["KX-1001", "KX-1002", "KX-1003", "KX-1004"]


@router.post("/api/workflow/queue")
def queue(body: QueueIn, request: Request):
    s = _session(request)
    try:
        return service.start_queue(s["token"], body.tickets)
    except service.WorkerNotReady as e:
        raise HTTPException(503, str(e))


@router.get("/api/workflow/queue")
def queue_state():
    return service.queue_state() or {"rows": [], "ok": 0, "total": len(service.expected_queue()), "done": False}


@router.get("/api/workflow/crashtest")
def crashtest_state():
    return crashtest.state()
