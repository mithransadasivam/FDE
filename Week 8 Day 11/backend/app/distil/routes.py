"""The Model lab's API (Day 11). Done: you do not change this file for a ticket."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.distil import reads as T
from app.distil import service

router = APIRouter()


class TrainRequest(BaseModel):
    read_files: list[str] = ["pilot"]
    name: str | None = None


class ActiveRequest(BaseModel):
    model: str


class CascadeRequest(BaseModel):
    model: str | None = None
    set: str = "october"
    threshold: float = service.DEFAULT_THRESHOLD
    spot: int = 5


@router.get("/api/distil/status")
def status():
    return service.status()


@router.get("/api/distil/reads/{name}")
def reads(name: str, only_disagree: bool = False, n: int = 12):
    if name not in T.READ_FILES:
        raise HTTPException(404, f"No reads called {name!r}")
    return {"summary": T.summary(name), "sample": T.sample(name, n, only_disagree)}


@router.post("/api/distil/train")
def train(req: TrainRequest):
    bad = [n for n in req.read_files if n not in T.READ_FILES]
    if bad or not req.read_files:
        raise HTTPException(400, f"Unknown reads: {bad}")
    if req.name and (not req.name.replace("-", "").replace("_", "").isalnum() or len(req.name) > 40):
        raise HTTPException(400, "A model name is letters, digits, - and _")
    try:
        return service.train(req.read_files, req.name)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/api/distil/active")
def active(req: ActiveRequest):
    if req.model not in [m["name"] for m in service.models()]:
        raise HTTPException(404, f"No model called {req.model!r}")
    service.set_active(req.model)
    return {"active": req.model}


@router.get("/api/distil/evaluate")
def evaluate(set: str = "october", model: str | None = None, threshold: float | None = None):
    return service.evaluate(model, set, threshold)


@router.get("/api/distil/documents/{doc_id}")
def document(doc_id: str, model: str | None = None):
    try:
        return service.document(doc_id, model)
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.post("/api/distil/cascade")
def cascade(req: CascadeRequest):
    if not 0 <= req.threshold <= 1:
        raise HTTPException(400, "The threshold is between 0 and 1")
    return service.cascade(req.model, req.set, req.threshold, req.spot)


@router.get("/api/distil/scale")
def scale(threshold: float = service.DEFAULT_THRESHOLD, model: str | None = None):
    return service.scale(model, threshold)


@router.get("/api/distil/drift")
def drift(threshold: float = service.DEFAULT_THRESHOLD, model: str | None = None):
    return service.drift(model, threshold)


@router.get("/api/distil/weights")
def weights(label: str = "statement_date", model: str | None = None):
    return {"label": label, "weights": service.weights(model, label)}
