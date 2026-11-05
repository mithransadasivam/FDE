"""Day 3 API: /api/cases/... for the UC1 prototype (the client's Cases screen), its demo and the PR review."""

from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import store
from app.config import DOCUMENTS_DIR
from app.llm import llm_client
from app.prototype import cases
from app.prototype.demo import run_demo

router = APIRouter(prefix="/api/cases")


def _app(case_id: str):
    apps = cases.applications()
    if case_id not in apps:
        raise HTTPException(404, f"No case {case_id}")
    return apps[case_id]


@router.get("")
def queue():
    """The analyst's queue. A case not read yet shows as "new"; opening it reads it."""
    out = []
    client = None
    for cid, app in cases.applications().items():
        row = {"case_id": cid, "applicant_name": app.applicant_name, "postcode": app.postcode,
               "received_date": app.received_date, "channel": app.channel, "state": "new",
               "issuer": "", "doubtful": 0, "decision": None}
        done = cases.decisions(cid)
        if done:
            row["decision"] = done[-1]["decision"]
        if cases.is_read(cid):
            client = client or llm_client()
            try:
                v = cases.case_view(cid, client)
                row["state"] = v["recommendation"]
                row["issuer"] = next(f["value"] for f in v["fields"] if f["name"] == "issuer")
                row["doubtful"] = sum(1 for f in v["fields"] if f["status"] not in ("ok", "confirmed"))
            except NotImplementedError as e:
                row["state"] = "not_built"
                row["detail"] = str(e)
        out.append(row)
    return out


@router.get("/demo")
def demo():
    return run_demo(llm_client())


@router.get("/pr-review")
def pr_review():
    r = store.load("reviews/latest.json", None)
    if r is None:
        raise HTTPException(404, "No review yet: run  python -m scripts.pr_review  from backend/")
    return r


@router.get("/{case_id}")
def case(case_id: str):
    _app(case_id)
    return cases.case_view(case_id, llm_client(), strict=False)


@router.get("/{case_id}/image")
def image(case_id: str):
    app = _app(case_id)
    return FileResponse(DOCUMENTS_DIR / app.document, media_type="image/jpeg")


class FieldAction(BaseModel):
    action: Literal["accept", "correct"]
    value: str = ""
    analyst_id: str


@router.post("/{case_id}/fields/{name}")
def field_action(case_id: str, name: str, body: FieldAction):
    _app(case_id)
    if not body.analyst_id.strip():
        raise HTTPException(422, "An analyst ID is required")
    view = cases.case_view(case_id, llm_client())
    current = next((f for f in view["fields"] if f["name"] == name), None)
    if current is None:
        raise HTTPException(404, f"No field {name}")
    value = current["value"] if body.action == "accept" else body.value.strip()
    if not value:
        raise HTTPException(422, "A corrected value cannot be empty")
    cases.log_field(case_id, name, body.action, value, body.analyst_id, current["value"])
    return cases.case_view(case_id, llm_client())


class Decision(BaseModel):
    decision: Literal["approve", "ask_applicant", "escalate"]
    analyst_id: str
    reason: str = ""


@router.post("/{case_id}/decision")
def decide(case_id: str, body: Decision):
    """A person makes every decision (SC4): no analyst ID, no decision. Approve needs every check to pass."""
    _app(case_id)
    if not body.analyst_id.strip():
        raise HTTPException(422, "An analyst ID is required: a person makes every decision")
    view = cases.case_view(case_id, llm_client())
    if body.decision == "approve" and view["recommendation"] != "ready":
        raise HTTPException(409, "Every check must pass before the document can be approved")
    if body.decision != "approve" and not body.reason.strip():
        raise HTTPException(422, "Give a reason for the applicant or for the escalation")
    cases.log_decision(case_id, body.decision, body.analyst_id, body.reason)
    return cases.case_view(case_id, llm_client())
