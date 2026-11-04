"""The Engagement Console API. Run it with:  python -m uvicorn app.main:app --reload --port 8000"""

import json
import os
import shutil

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app import store
from app.config import CRITERIA_DRAFT_FILE, DOCS_DIR, ENGAGEMENT_DIR, TRANSCRIPT_FILE
from app.discovery.brief import load_brief
from app.discovery.criteria import check_criterion
from app.discovery.findings import extract_findings, verify_evidence
from app.discovery.models import Criterion, Finding, Question, UseCase
from app.discovery.questions import draft_questions
from app.discovery.summary import build_summary
from app.discovery.usecases import load_candidates, score_use_case
from app.llm import LLMError, llm_client

if os.getenv("FDE_RESET_ON_START") == "1" and ENGAGEMENT_DIR.exists():
    shutil.rmtree(ENGAGEMENT_DIR)  # only the end-to-end tests set this, on their own folder

app = FastAPI(title="FDE Engagement Console")

# Day 2: solution design screens
from app.design.routes import router as design_router  # noqa: E402

app.include_router(design_router)


@app.exception_handler(NotImplementedError)
async def not_built(_: Request, exc: NotImplementedError):
    return JSONResponse(status_code=501, content={"detail": str(exc) or "Not built yet"})


@app.exception_handler(LLMError)
async def llm_failed(_: Request, exc: LLMError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/api/health")
def health():
    return {"status": "ok", "fake_llm": os.getenv("FDE_FAKE_LLM") == "1"}


# ---------------------------------------------------------------- brief and question plan
@app.get("/api/brief")
def brief():
    return load_brief()


@app.get("/api/questions")
def questions():
    return store.load("question_plan.json", [])


@app.post("/api/questions/draft")
def questions_draft():
    qs = draft_questions(load_brief()["markdown"], llm_client())
    data = [q.model_dump() for q in qs]
    store.save("question_plan.json", data)
    return data


class Star(BaseModel):
    starred: bool


@app.put("/api/questions/{qid}")
def question_star(qid: str, body: Star):
    data = store.load("question_plan.json", [])
    for q in data:
        if q["id"] == qid:
            q["starred"] = body.starred
            store.save("question_plan.json", data)
            return q
    raise HTTPException(404, f"No question {qid}")


# ---------------------------------------------------------------- interview notes
class Notes(BaseModel):
    text: str


@app.get("/api/notes")
def notes():
    return {"text": store.load_text("interview_notes.md")}


@app.put("/api/notes")
def notes_save(body: Notes):
    store.save_text("interview_notes.md", body.text)
    return {"saved": True, "words": len(body.text.split())}


# ---------------------------------------------------------------- findings (ENG-101)
@app.get("/api/findings")
def findings():
    return store.load("findings.json", [])


@app.post("/api/findings/extract")
def findings_extract():
    transcript = TRANSCRIPT_FILE.read_text(encoding="utf-8")
    found = extract_findings(transcript, llm_client())
    checked = verify_evidence(found, transcript)
    data = [f.model_dump() for f in checked]
    store.save("findings.json", data)
    return data


class Review(BaseModel):
    review: str


@app.put("/api/findings/{fid}")
def finding_review(fid: str, body: Review):
    data = store.load("findings.json", [])
    for f in data:
        if f["id"] == fid:
            f["review"] = Finding(**{**f, "review": body.review}).review
            store.save("findings.json", data)
            return f
    raise HTTPException(404, f"No finding {fid}")


# ---------------------------------------------------------------- success criteria (ENG-102)
def _criteria() -> list[Criterion]:
    data = store.load("success_criteria.json", None)
    if data is None:
        data = json.loads(CRITERIA_DRAFT_FILE.read_text(encoding="utf-8"))
        store.save("success_criteria.json", data)
    return [Criterion(**c) for c in data]


def _problems(c: Criterion) -> list[str]:
    try:
        return check_criterion(c)
    except NotImplementedError:
        return ["not checked yet: ticket ENG-102"]


def _with_problems(cs: list[Criterion]) -> list[dict]:
    return [{**c.model_dump(), "problems": _problems(c)} for c in cs]


@app.get("/api/criteria")
def criteria():
    return _with_problems(_criteria())


@app.put("/api/criteria/{cid}")
def criterion_save(cid: str, body: Criterion):
    cs = [c for c in _criteria() if c.id != cid]
    cs.append(body.model_copy(update={"id": cid}))
    cs.sort(key=lambda c: c.id)
    store.save("success_criteria.json", [c.model_dump() for c in cs])
    return _with_problems(cs)


@app.delete("/api/criteria/{cid}")
def criterion_delete(cid: str):
    cs = [c for c in _criteria() if c.id != cid]
    store.save("success_criteria.json", [c.model_dump() for c in cs])
    return _with_problems(cs)


# ---------------------------------------------------------------- use cases
def _use_cases() -> list[UseCase]:
    saved = {u["id"]: u for u in store.load("use_cases.json", [])}
    return [UseCase(**{**u.model_dump(), **saved.get(u.id, {})}) for u in load_candidates()]


@app.get("/api/usecases")
def use_cases():
    return [{**u.model_dump(), "score": score_use_case(u)} for u in _use_cases()]


class UseCaseEdit(BaseModel):
    value: int | None = None
    feasibility: int | None = None
    risk: int | None = None
    first_choice: bool | None = None


@app.put("/api/usecases/{uid}")
def use_case_edit(uid: str, body: UseCaseEdit):
    us = _use_cases()
    if uid not in {u.id for u in us}:
        raise HTTPException(404, f"No use case {uid}")
    changes = body.model_dump(exclude_none=True)
    out = []
    for u in us:
        if u.id == uid:
            if changes.get("first_choice") and u.excluded_reason:
                raise HTTPException(409, f"{u.name} is out of scope: {u.excluded_reason}")
            u = UseCase(**{**u.model_dump(), **changes})
        elif changes.get("first_choice"):
            u = u.model_copy(update={"first_choice": False})
        out.append(u)
    store.save("use_cases.json", [u.model_dump() for u in out])
    return [{**u.model_dump(), "score": score_use_case(u)} for u in out]


# ---------------------------------------------------------------- summary
@app.post("/api/summary/export")
def summary_export():
    fs = [Finding(**f) for f in store.load("findings.json", [])]
    md = build_summary(fs, _criteria(), _use_cases())
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "DISCOVERY_SUMMARY.md").write_text(md, encoding="utf-8")
    return {"path": "docs/DISCOVERY_SUMMARY.md", "markdown": md}
