"""Day 4 API: /api/eval/... for the Evaluation screen."""

from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import store
from app.config import DOCS_DIR, GUIDELINES_V0_FILE
from app.evaluation import service
from app.llm import llm_client
from app.prototype.cases import document_dir, ocr_words, read_document
from app.prototype.grounding import ground_fields
from app.prototype.rules import load_rules

router = APIRouter(prefix="/api/eval")
GUIDELINES_FILE = DOCS_DIR / "eval" / "LABELLING_GUIDELINES.md"


# ------------------------------------------------------------------ runs and error analysis (ENG-402)
class RunRequest(BaseModel):
    prompt: str = "extract"
    set: Literal["real", "synthetic", "all"] = "real"


@router.post("/runs")
def run(body: RunRequest):
    return service.run_set(body.set, body.prompt, llm_client())


@router.get("/runs")
def runs():
    return service.list_runs()


@router.get("/runs/{name}")
def run_get(name: str):
    r = store.load(f"eval/runs/{name}.json", None)
    if r is None:
        raise HTTPException(404, f"No run {name}")
    return r


@router.get("/tags")
def tags():
    t = store.load("eval/tags.json", {})
    return {"tags": t, "taxonomy": service.taxonomy(t)}


class Tag(BaseModel):
    key: str  # "<case_id>|<field>"
    type: str


@router.put("/tags")
def tag(body: Tag):
    t = store.load("eval/tags.json", {})
    t[body.key] = body.type.strip()
    if not t[body.key]:
        del t[body.key]
    store.save("eval/tags.json", t)
    return {"tags": t, "taxonomy": service.taxonomy(t)}


@router.get("/tom-tags")
def tom_tags():
    tags_ = service.tom_tags()
    return {"tags": tags_, "taxonomy": service.taxonomy({f"{t['case_id']}|{t['field']}": t["failure_type"] for t in tags_})}


# ------------------------------------------------------------------ labelling and agreement (ENG-401)
@router.get("/labelling")
def labelling():
    mine = store.load("eval/my_labels.json", {})
    client = llm_client()
    rules = load_rules()
    out = []
    for it in service.labelling_items():
        box = None
        try:
            fs = ground_fields(read_document(it["case_id"], client, "extract"), ocr_words(it["case_id"]), rules["ok_at"], rules["check_at"])
            box = next(f.box for f in fs if f.name == it["field"])
        except NotImplementedError:
            pass
        out.append({**it, "label": mine.get(it["item"]), "box": box, "image": f"/api/eval/docs/{it['case_id']}/image"})
    guide = GUIDELINES_FILE.read_text(encoding="utf-8") if GUIDELINES_FILE.exists() else GUIDELINES_V0_FILE.read_text(encoding="utf-8")
    return {"items": out, "guidelines": guide, "guideline_version": "docs/eval/LABELLING_GUIDELINES.md" if GUIDELINES_FILE.exists() else "v0 (data/)",
            "rounds": store.load("eval/label_rounds.json", [])}


class Label(BaseModel):
    label: Literal["correct", "wrong"]


@router.put("/labelling/{item}")
def label(item: str, body: Label):
    mine = store.load("eval/my_labels.json", {})
    mine[item] = body.label
    store.save("eval/my_labels.json", mine)
    return mine


@router.post("/labelling/compare")
def compare():
    mine = store.load("eval/my_labels.json", {})
    if len(mine) < len(service.labelling_items()):
        raise HTTPException(409, "Label every item before you compare with Tom")
    return service.compare_labels(mine, "v1 (docs/eval)" if GUIDELINES_FILE.exists() else "v0")


@router.post("/labelling/reset")
def reset_labels():
    store.save("eval/my_labels.json", {})
    return {}


# ------------------------------------------------------------------ judges (uses ENG-401)
@router.get("/judges")
def judges():
    prompts = service.judge_prompts()
    results = {s: store.load(f"eval/judges/{s}.json", None) for ss in prompts.values() for s in ss}
    return {"judges": [{"judge": j, "field": f, "failure_type": t, "prompts": prompts[j]} for j, (f, t) in service.JUDGES.items()],
            "results": {k: v for k, v in results.items() if v}}


@router.post("/judges/{stem}/run")
def judge_run(stem: str):
    if not any(stem in ss for ss in service.judge_prompts().values()):
        raise HTTPException(404, f"No judge prompt evals/judges/{stem}.md")
    return service.run_judge(stem, llm_client())


# ------------------------------------------------------------------ synthetic cases
class SynRequest(BaseModel):
    slice: Literal["two_dates", "joint_names", "issuer_variant", "address_order"]
    n: int = 20


@router.post("/synthetic")
def synthetic(body: SynRequest):
    return {"made": service.make_synthetic(body.slice, body.n, llm_client())}


@router.get("/synthetic")
def synthetic_list():
    return [{"case_id": k, "slices": v["slices"], "labels": v["labels"]} for k, v in service.synthetic_cases().items()]


# ------------------------------------------------------------------ document images
@router.get("/docs/{case_id}/image")
def image(case_id: str):
    p = document_dir(case_id) / f"{case_id}.jpg"
    if not p.exists():
        raise HTTPException(404, f"No image for {case_id}")
    return FileResponse(p, media_type="image/jpeg")
