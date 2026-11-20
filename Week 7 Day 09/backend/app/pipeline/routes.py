"""Day 6 API: /api/pipeline/… for the Documents screen."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.pipeline import documents as D
from app.pipeline import service

router = APIRouter(prefix="/api/pipeline")


class RunRequest(BaseModel):
    set: str = "october"
    prompts: list[str]
    concurrency: int = 8


class RouteRequest(BaseModel):
    set: str = "october"
    parser_prompt: str = "extract_v2"
    vision_prompt: str = ""
    ok_at: float = 0.85
    use_agreement: bool = True


class BatchRequest(RouteRequest):
    concurrency: int = 8
    resume: bool = False


class ReviewRequest(BaseModel):
    set: str = "october"
    doc_id: str
    field: str
    action: str  # accept | correct
    value: str
    analyst_id: str = "tom-team"


@router.get("/status")
def status():
    return service.status()


@router.get("/documents")
def documents(set: str = "october"):
    try:
        return service.documents(set)
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.get("/documents/{doc_id}")
def document(doc_id: str):
    try:
        return service.document(doc_id)
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.get("/documents/{doc_id}/image")
def image(doc_id: str):
    try:
        return FileResponse(D.page_image(doc_id), media_type="image/jpeg")
    except KeyError as e:
        raise HTTPException(404, str(e))


@router.post("/run")
def run(req: RunRequest):
    return service.run(req.set, req.prompts, max(1, min(req.concurrency, 64)))


@router.get("/compare")
def compare(set: str = "october"):
    return service.compare(set)


@router.post("/routing")
def routing(req: RouteRequest):
    return service.routing(req.set, req.parser_prompt, req.vision_prompt, req.ok_at, req.use_agreement)


@router.get("/routing/settings")
def routing_settings(set: str = "october"):
    return service.routing_settings(set)


@router.get("/queue")
def queue(set: str = "october"):
    return service.queue(set)


@router.post("/review")
def review(req: ReviewRequest):
    if req.action not in ("accept", "correct"):
        raise HTTPException(400, "action must be accept or correct")
    return service.review(req.set, req.doc_id, req.field, req.action, req.value, req.analyst_id)


@router.post("/batch")
def batch(req: BatchRequest):
    return service.batch(req.set, req.parser_prompt, req.vision_prompt, max(1, min(req.concurrency, 64)), req.ok_at, req.use_agreement, req.resume)


@router.get("/batch")
def last_batch(set: str = "october"):
    return service.last_batch(set) or {}
