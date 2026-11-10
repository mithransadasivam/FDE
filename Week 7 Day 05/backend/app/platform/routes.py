"""Day 5 API: /api/pilot/... for the Pilot screen."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.platform import guardrail as g
from app.platform import service

router = APIRouter(prefix="/api/pilot")


@router.get("/status")
def status():
    return service.status()


class CaseRequest(BaseModel):
    case_id: str = "D03-001"


@router.post("/selftest")
def selftest(body: CaseRequest):
    return service.selftest(body.case_id)


@router.post("/try")
def try_case(body: CaseRequest):
    return service.try_case(body.case_id)


@router.get("/plan")
def plan():
    p = service.plan_checks()
    if p is None:
        raise HTTPException(404, "No infra/pilot.plan.json yet: run terraform plan, then terraform show -json (slide 15)")
    return p


@router.get("/guardrails")
def guardrails():
    return service.guardrails()


@router.post("/guardrails/{policy}/probes")
def probes(policy: str):
    if policy not in g.list_policies():
        raise HTTPException(404, f"No guardrail policy infra/guardrails/{policy}.json")
    return service.run_probes(policy)


@router.get("/spend")
def spend():
    return service.spend()
