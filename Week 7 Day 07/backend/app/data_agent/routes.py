"""Day 7 API: /api/data/… for the Ask the data and Data agent screens."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.data_agent import service
from app.data_agent.agent import UnknownQuestion

router = APIRouter(prefix="/api/data")


class AskRequest(BaseModel):
    question: str
    user: str
    layer: str | None = None


class LayerRequest(BaseModel):
    layer: str


class EvalRequest(BaseModel):
    set: str = "bank30"
    layer: str = "caseflow_v1"


@router.get("/status")
def status():
    return service.status()


@router.get("/warehouse")
def warehouse(layer: str = ""):
    try:
        return service.warehouse_view(layer or service.current_layer())
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.get("/layers/{name}")
def layer(name: str):
    try:
        return service.layer(name)
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.put("/settings")
def settings(body: LayerRequest):
    try:
        return service.set_layer(body.layer)
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.get("/suggestions")
def suggestions(user: str):
    return service.suggestions(user)


@router.post("/ask")
def ask(body: AskRequest):
    if not body.question.strip():
        raise HTTPException(400, "Type a question first")
    try:
        return service.ask(body.question, body.user, body.layer)
    except UnknownQuestion as e:
        raise HTTPException(400, str(e))
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.get("/probes")
def probes():
    return service.probes()


@router.get("/rowchecks")
def rowchecks():
    return service.row_checks()


@router.get("/eval")
def eval_view(set: str = "bank30"):
    try:
        return service.eval_view(set)
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.post("/eval/run")
def eval_run(body: EvalRequest):
    try:
        return service.eval_run(body.set, body.layer)
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.get("/eval/results")
def eval_results(set: str = "bank30", layer: str = "caseflow_v1"):
    r = service.eval_results(set, layer)
    if r is None:
        raise HTTPException(404, f"No run of {set} with {layer} yet")
    return r
