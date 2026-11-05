"""Day 2 API: /api/design/..."""

import json

from fastapi import APIRouter, HTTPException

from app import store
from app.config import ADR_DIR
from app.design.adr import check_adr
from app.design.architecture import RULES, check_architecture, load_options
from app.design.cost import estimate, load_prices, value_per_month
from app.design.plan import check_plan
from app.design.profile import load_dictionary, load_sample, profile_column, readiness

router = APIRouter(prefix="/api/design")

DEFAULT_RULES = {"engagement_weeks": 6, "validation_weeks": 3, "production_gate_approver": "Helen Achebe",
                 "stakeholders": ["Martin Hale", "Deborah Okafor", "Helen Achebe", "Tom Reyes"]}


# ---------------------------------------------------------------- data readiness (ENG-201)
@router.get("/sample")
def sample_info():
    rows = load_sample()
    return {"file": "data/Day02_Slide10_caseflow_poa_sample.csv", "rows": len(rows),
            "columns": [s.model_dump() for s in load_dictionary().values()], "preview": rows[:8]}


@router.post("/profile")
def profile():
    rows = load_sample()
    specs = load_dictionary()
    profiles = [profile_column(spec, [r.get(col) for r in rows]) for col, spec in specs.items()]
    result = {"rows": len(rows), "profiles": [p.model_dump() for p in profiles], "readiness": readiness(rows, profiles)}
    store.save("data_readiness.json", result)
    return result


@router.get("/profile")
def profile_saved():
    return store.load("data_readiness.json", None)


# ---------------------------------------------------------------- architectures (ENG-202)
def _checked(a):
    try:
        return [v.model_dump() for v in check_architecture(a)]
    except NotImplementedError:
        return None


@router.get("/options")
def options():
    try:
        opts = load_options()
    except Exception as e:  # a broken JSON file should not take the screen down
        raise HTTPException(422, f"An architecture file is not valid: {e}")
    return {"rules": [{"rule": r, "text": t, "source": s} for r, t, s in RULES],
            "options": [{**a.model_dump(by_alias=False), "violations": _checked(a)} for a in opts]}


# ---------------------------------------------------------------- run-cost
@router.get("/cost")
def cost(docs: float = 8600, pages: float = 1.4, minutes_saved: float = 3.0):
    p = load_prices()
    opts = load_options()
    rows = [{"id": a.id, "name": a.name, **estimate(a.cost, docs, pages, p)} for a in opts]
    curve_points = [1000, 2500, 5000, 8600, 12500, 17200, 25000, 50000, 100000]
    curve = [{"docs": n, **{a.id: estimate(a.cost, n, pages, p)["total_gbp"] for a in opts}} for n in curve_points]
    return {"inputs": {"docs": docs, "pages": pages, "minutes_saved": minutes_saved},
            "options": rows, "curve": curve, "value_gbp": value_per_month(docs, minutes_saved, p), "prices": p}


# ---------------------------------------------------------------- ADRs
@router.get("/adrs")
def adrs():
    ADR_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for f in sorted(ADR_DIR.glob("ADR-*.md")):
        md = f.read_text(encoding="utf-8")
        out.append({"file": f"docs/adr/{f.name}", "markdown": md, "checks": check_adr(md)})
    return out


# ---------------------------------------------------------------- delivery plan
@router.get("/plan")
def plan():
    rules = store.load("client_rules.json", DEFAULT_RULES)
    p = store.load("delivery_plan.json", None)
    return {"rules": rules, "plan": p, "checks": check_plan(p, rules) if p else None}
