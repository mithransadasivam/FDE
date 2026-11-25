"""What the Model lab screen shows (done: you do not change this file for a ticket).

The three tickets are word_labels() (ENG-1101), read_fields() (ENG-1102) and route_document() (ENG-1103).
Everything here calls them. Scores always compare with the bank's double-keyed answers (Tom's labels, Day 6),
never with the teacher: the teacher is what we are trying to do without.
"""

import inspect
import json
import time
from functools import lru_cache
from statistics import median

from app import store
from app.config import SCALE_FILE_11
from app.distil import cascade as C
from app.distil import labels as L
from app.distil import model as M
from app.distil import reader as R
from app.distil import reads as T
from app.distil.drift import retrain_candidates
from app.llm import llm_client
from app.pipeline import documents as D
from app.pipeline.methods import read as pipeline_read
from app.pipeline.parse import parse_document
from app.pipeline.routing import OK_AT, route_field
from app.pipeline.service import GBP_PER_USD, PILOT_MODEL, usd
from app.prototype.models import FIELD_LABELS, FIELDS, Field

PARSER, VISION = "extract_v2", "extract_vlm_v1"  # ADR-003: the pilot's two readings
GRID = [0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
DEFAULT_THRESHOLD = 0.7


def norm(text: str) -> str:
    return T.norm(text)


# ---------------------------------------------------------------- tickets, models, status
def tickets_built() -> dict:
    """Which of today's tickets are built, judged by running each one on a small example."""
    from app.prototype.models import OcrWord
    import numpy as np
    ok = {}
    read = {"words": [["w001", "Mr", 0, 0, 0.1, 0.1, 1.0], ["w002", "Ali", 0.1, 0, 0.2, 0.1, 1.0]],
            "parser": {f: {"value": "Mr Ali" if f == "full_name" else "x", "word_ids": ["w001", "w002"] if f == "full_name" else ["w002"]}
                       for f in FIELDS},
            "vision": {f: ("Mr Ali" if f == "full_name" else "x") for f in FIELDS}}
    try:
        read2 = json.loads(json.dumps(read))
        read2["vision"]["statement_date"] = "y"
        ok["ENG-1101"] = L.word_labels(read2) is None
    except Exception:
        ok["ENG-1101"] = False
    try:
        words = [OcrWord(id="w001", text="01", box=[0, 0, 1, 1], confidence=0.5)]
        probs = np.array([[0.0, 0.0, 0.0, 1.0, 0.0]])
        f = R.read_fields(words, probs, ["O", "full_name", "address", "statement_date", "issuer"])
        ok["ENG-1102"] = abs(f[2].confidence - 0.5) < 1e-6
    except Exception:
        ok["ENG-1102"] = False
    try:
        fs = [R.SmallField(name=n, label=n, value="v", word_ids=["w1"], confidence=0.99) for n in FIELDS]
        fs[2] = R.SmallField(name="statement_date", label="x", value="v", word_ids=["w1"], confidence=0.6)
        ok["ENG-1103"] = C.route_document(fs, 0.8).route == "teacher"
    except Exception:
        ok["ENG-1103"] = False
    return ok


def models() -> list[dict]:
    p = store.path("distil/models")
    out = []
    for f in sorted(p.glob("*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                head = fh.read(4000)
            meta = json.loads(head[head.index('"meta":') + 7: head.index(',\n "features"')])
            meta["size_kb"] = round(f.stat().st_size / 1024)
            run = store.load(f"distil/runs/{f.stem}.json", {}).get("meta", {})
            if run.get("at") == meta["at"]:
                meta["october"] = run.get("october")
            out.append(meta)
        except Exception:
            continue
    return sorted(out, key=lambda m: m["at"])


def active_name() -> str | None:
    a = store.load("distil/active.json", {}).get("model")
    names = [m["name"] for m in models()]
    return a if a in names else (names[-1] if names else None)


def set_active(name: str) -> None:
    store.save("distil/active.json", {"model": name})


@lru_cache(maxsize=8)
def _model(name: str, _mtime: float):
    return M.load(name)


def get_model(name: str | None = None):
    name = name or active_name()
    if not name:
        return None
    p = store.path(f"distil/models/{name}.json")
    return _model(name, p.stat().st_mtime) if p.exists() else None


def status() -> dict:
    return {"tickets": tickets_built(), "models": models(), "active": active_name(),
            "read_files": [T.summary(n) for n in T.READ_FILES], "sets": [{"name": s["name"], "label": s.get("label", "")} for s in D.sets()],
            "threshold": store.load("distil/settings.json", {}).get("threshold", DEFAULT_THRESHOLD), "volumes": volumes()}


def train(read_files: list[str], name: str | None = None) -> dict:
    names = [m["name"] for m in models()]
    name = name or f"small-{len(names) + 1}"
    m = M.train(name, T.load_many(read_files), read_files)
    set_active(name)
    report = evaluate(name, "october")
    meta = dict(m.meta, october=report["overall"])
    store.save(f"distil/runs/{name}.json", {"meta": meta})
    return meta


# ---------------------------------------------------------------- reading with the small model
_WORDS: dict[str, tuple] = {}


def words(doc_id: str):
    if doc_id not in _WORDS:
        p = parse_document(doc_id)
        _WORDS[doc_id] = (p.words, p.source)
    return _WORDS[doc_id]


def small_read(model, doc_id: str, kind: str) -> dict:
    ws, source = words(doc_id)
    t0 = time.perf_counter()
    probs = model.probs(ws, kind)
    fields = R.read_fields(ws, probs, model.classes)
    ms = (time.perf_counter() - t0) * 1000
    return {"fields": fields, "probs": probs, "ms": ms, "source": source}


def evaluate(model_name: str | None, set_name: str, threshold: float | None = None) -> dict:
    """The small model alone on a keyed set: every field, against Tom's labels."""
    model = get_model(model_name)
    if model is None:
        return {"model": None}
    threshold = threshold if threshold is not None else DEFAULT_THRESHOLD
    labels, slices = D.labels(set_name), D.slices(set_name)
    man = {r["doc_id"]: r for r in D.manifest(set_name)}
    rows, ms = [], []
    for d in sorted(labels):
        r = small_read(model, d, man[d]["kind"])
        ms.append(r["ms"])
        for f in r["fields"]:
            exp = labels[d].get(f.name, "")
            rows.append({"doc_id": d, "kind": man[d]["kind"], "slices": slices[d], "field": f.name, "label": f.label, "value": f.value,
                         "confidence": f.confidence, "expected": exp, "correct": norm(f.value) == norm(exp)})

    def acc(rs):
        return {"fields": len(rs), "right": sum(r["correct"] for r in rs),
                "accuracy": round(100 * sum(r["correct"] for r in rs) / len(rs), 1) if rs else None}
    errors = [r for r in rows if not r["correct"]]
    return {"model": model.meta["name"], "set": set_name, "threshold": threshold, "documents": len(labels), "overall": acc(rows),
            "per_field": {f: acc([r for r in rows if r["field"] == f]) for f in FIELDS},
            "per_kind": {k: acc([r for r in rows if r["kind"] == k]) for k in sorted({r["kind"] for r in rows})},
            "per_slice": {s: acc([r for r in rows if s in r["slices"]]) for s in sorted({s for r in rows for s in r["slices"]})},
            "confident_errors": sum(r["confidence"] >= threshold for r in errors),
            "errors": sorted(errors, key=lambda r: -r["confidence"])[:60],
            "ms_per_doc": round(median(ms), 1) if ms else None, "model_meta": model.meta}


def document(doc_id: str, model_name: str | None = None) -> dict:
    """One document through the small model: each word's most likely label, the four fields, the keyed answers."""
    model = get_model(model_name)
    set_name = D.set_of(doc_id)
    row = D.doc_row(doc_id)
    ws, source = words(doc_id)
    out = {"doc_id": doc_id, "set": set_name, "kind": row["kind"], "source": source, "image": f"/api/pipeline/documents/{doc_id}/image",
           "expected": D.labels(set_name).get(doc_id, {}), "slices": D.slices(set_name).get(doc_id, [])}
    if model is None:
        return {**out, "model": None, "words": [w.model_dump() for w in ws]}
    r = small_read(model, doc_id, row["kind"])
    probs = r["probs"]
    out["words"] = [{**w.model_dump(), "label": model.classes[int(probs[i].argmax())], "p": round(float(probs[i].max()), 3)}
                    for i, w in enumerate(ws)]
    out["fields"] = [dict(f.model_dump(), correct=norm(f.value) == norm(out["expected"].get(f.name, ""))) for f in r["fields"]]
    th = store.load("distil/settings.json", {}).get("threshold", DEFAULT_THRESHOLD)
    out["decision"] = C.route_document(r["fields"], th).model_dump()
    out["threshold"] = th
    out["model"] = model.meta["name"]
    out["ms"] = round(r["ms"], 1)
    return out


# ---------------------------------------------------------------- the pilot as the teacher (ADR-003)
def teacher_doc(doc_id: str, client) -> dict:
    """The pilot's answer for one document: both readings, and ADR-003's routing of every field."""
    p, v = pipeline_read(doc_id, PARSER, client), pipeline_read(doc_id, VISION, client)
    pf = {f["name"]: Field(**f) for f in p["fields"]}
    vf = {f["name"]: Field(**f) for f in v["fields"]}
    fields = []
    for name in FIELDS:
        rt = route_field(pf[name], vf.get(name), OK_AT, True)
        fields.append({"name": name, "value": pf[name].value, "decision": rt.decision, "reasons": rt.reasons})
    tin = p["usage"]["input_tokens"] + v["usage"]["input_tokens"]
    tout = p["usage"]["output_tokens"] + v["usage"]["output_tokens"]
    return {"fields": fields, "ms": max(p["usage"]["latency_ms"], v["usage"]["latency_ms"]), "calls": 2,
            "usd": usd(tin, tout, PILOT_MODEL) or 0.0}


# ---------------------------------------------------------------- the cascade (ENG-1103)
def _small_all(model, set_name: str) -> dict:
    man = {r["doc_id"]: r for r in D.manifest(set_name)}
    return {d: small_read(model, d, man[d]["kind"]) for d in sorted(D.labels(set_name))}


def _cascade_rows(model, set_name: str, threshold: float, spot: int, client, smalls: dict | None = None) -> list[dict]:
    labels = D.labels(set_name)
    man = {r["doc_id"]: r for r in D.manifest(set_name)}
    smalls = smalls or _small_all(model, set_name)
    rows = []
    for d in sorted(labels):
        s = smalls[d]
        dec = C.route_document(s["fields"], threshold)
        checked = dec.route == "small" and spot and C.spot_check(d, spot)
        row = {"doc_id": d, "kind": man[d]["kind"], "route": dec.route, "reasons": dec.reasons or (["spot check"] if checked else []),
               "spot": bool(checked), "small_ms": s["ms"],
               "small": [{"name": f.name, "value": f.value, "confidence": f.confidence} for f in s["fields"]]}
        if dec.route == "teacher" or checked:
            t = teacher_doc(d, client)
            row["teacher"] = t
            if checked:  # the small model's values still go through: the check only compares
                row["agree"] = sum(norm(a["value"]) == norm(b["value"]) for a, b in zip(row["small"], t["fields"]))
        final = []
        for i, name in enumerate(FIELDS):
            exp = labels[d].get(name, "")
            if dec.route == "small":
                v, how = row["small"][i]["value"], "small"
            else:
                tf = row["teacher"]["fields"][i]
                v, how = tf["value"], ("person" if tf["decision"] == "review" else "teacher")
            final.append({"name": name, "value": v, "how": how, "expected": exp, "correct": norm(v) == norm(exp)})
        row["final"] = final
        rows.append(row)
    return rows


def _stats(rows: list[dict]) -> dict:
    fields = [f for r in rows for f in r["final"]]
    n = len(fields) or 1
    teacher = [r for r in rows if "teacher" in r]
    slipped = [dict(f, doc_id=r["doc_id"]) for r in rows for f in r["final"] if f["how"] != "person" and not f["correct"]]
    small_ms = [r["small_ms"] for r in rows]
    counter_ms = [r["small_ms"] if r["route"] == "small" else r["small_ms"] + r["teacher"]["ms"] for r in rows]
    spot = [r for r in rows if r["spot"]]
    return {"documents": len(rows), "small_docs": sum(r["route"] == "small" for r in rows),
            "teacher_docs": sum(r["route"] == "teacher" for r in rows), "spot_checks": len(spot),
            "teacher_share": round(len(teacher) / len(rows), 3) if rows else 0, "sonnet_calls": 2 * len(teacher),
            "to_person": sum(f["how"] == "person" for f in fields), "to_person_pct": round(100 * sum(f["how"] == "person" for f in fields) / n, 1),
            "slipped": len(slipped), "slipped_small": sum(1 for r in rows for f in r["final"] if f["how"] == "small" and not f["correct"]),
            "accuracy_after_review": round(100 * (n - len(slipped)) / n, 1), "slipped_items": slipped[:40],
            "spot_agree": sum(r.get("agree", 0) for r in spot), "spot_fields": 4 * len(spot),
            "usd_per_doc": round(sum(r["teacher"]["usd"] for r in teacher) / len(rows), 6) if rows else 0,
            "small_ms_p50": round(median(small_ms), 1) if rows else None,
            "counter_ms_p50": round(median(counter_ms)) if rows else None,
            "counter_ms_p90": round(sorted(counter_ms)[int(0.9 * (len(counter_ms) - 1))]) if rows else None}


def pilot_alone(set_name: str, client=None) -> dict:
    """ADR-003 on its own: the pilot reads every document (the baseline the cascade must not be worse than)."""
    client = client or llm_client()
    labels = D.labels(set_name)
    rows = []
    for d in sorted(labels):
        t = teacher_doc(d, client)
        final = [{"name": f["name"], "value": f["value"], "how": "person" if f["decision"] == "review" else "teacher",
                  "expected": labels[d].get(f["name"], ""), "correct": norm(f["value"]) == norm(labels[d].get(f["name"], ""))} for f in t["fields"]]
        rows.append({"doc_id": d, "route": "teacher", "teacher": t, "final": final, "spot": False, "small_ms": 0.0})
    return _stats(rows)


def cascade(model_name: str | None, set_name: str, threshold: float, spot: int = 5, client=None, save: bool = True) -> dict:
    model = get_model(model_name)
    if model is None:
        return {"model": None}
    client = client or llm_client()
    if save:
        store.save("distil/settings.json", {"threshold": threshold})
    smalls = _small_all(model, set_name)
    rows = _cascade_rows(model, set_name, threshold, spot, client, smalls)
    curve = []
    for t in GRID:
        rs = _cascade_rows(model, set_name, t, 0, client, smalls)
        s = _stats(rs)
        curve.append({"threshold": t, **{k: s[k] for k in ["teacher_share", "slipped", "to_person_pct", "accuracy_after_review", "sonnet_calls"]}})
    reasons: dict[str, int] = {}
    for r in rows:
        if r["route"] == "teacher":
            for x in r["reasons"]:
                k = x.split(" ")[0] + (" missing" if x.endswith("missing") else " low")
                reasons[k] = reasons.get(k, 0) + 1
    out = {"model": model.meta["name"], "set": set_name, "threshold": threshold, "spot_per_hundred": spot, **_stats(rows),
           "pilot": pilot_alone(set_name, client), "curve": curve, "reasons": reasons,
           "rows": [{k: r[k] for k in ("doc_id", "kind", "route", "reasons", "spot")} for r in rows],
           "retrain": retrain_safe(rows)}
    store.save(f"distil/cascade_{set_name}.json", {k: v for k, v in out.items() if k != "rows"})
    return out


def retrain_safe(rows: list[dict]):
    try:
        return retrain_candidates([{k: r[k] for k in ("doc_id", "kind", "route", "reasons")} for r in rows])
    except NotImplementedError:
        return None


# ---------------------------------------------------------------- client scale (Activity 4)
def volumes() -> dict:
    return json.loads(SCALE_FILE_11.read_text(encoding="utf-8")) if SCALE_FILE_11.exists() else {}


def scale(model_name: str | None, threshold: float) -> dict:
    """The month at the bank's volumes, from the October numbers: the pilot alone (ADR-003) against the cascade."""
    v = volumes()
    c = cascade(model_name, "october", threshold, save=False)
    if c.get("model") is None:
        return {"model": None}
    p = c["pilot"]
    fixed = v["small_model_host_gbp_per_month"] + v["upkeep_hours_per_month"] * v["engineer_gbp_per_hour"]

    per_check = v["analyst_seconds_per_field_check"] / 3600 * v["analyst_gbp_per_hour"]

    def month(docs, s, fixed_gbp=0):
        checks = round(docs * 4 * s["to_person_pct"] / 100)
        model_gbp = docs * s["usd_per_doc"] * GBP_PER_USD
        return {"documents": docs, "sonnet_calls": round(docs * s["sonnet_calls"] / s["documents"]),
                "model_gbp": round(model_gbp), "fixed_gbp": fixed_gbp, "fields_to_person": checks,
                "people_gbp": round(checks * per_check), "people_hours": round(checks * v["analyst_seconds_per_field_check"] / 3600),
                "total_gbp": round(model_gbp + fixed_gbp + checks * per_check)}
    volumes_ = {"today": v["business_as_usual_docs_per_month"], "remediation": v["business_as_usual_docs_per_month"] + v["remediation_docs_per_month"]}
    saving_per_doc = (p["usd_per_doc"] - c["usd_per_doc"]) * GBP_PER_USD + 4 * (p["to_person_pct"] - c["to_person_pct"]) / 100 * per_check
    breakeven = round(fixed / saving_per_doc) if saving_per_doc > 0 else None
    return {"model": c["model"], "threshold": threshold, "volumes": v, "fixed_gbp": fixed,
            "october": {"pilot": {k: p[k] for k in ("slipped", "to_person_pct", "accuracy_after_review", "usd_per_doc", "counter_ms_p50", "sonnet_calls")},
                        "cascade": {k: c[k] for k in ("slipped", "to_person_pct", "accuracy_after_review", "usd_per_doc", "counter_ms_p50",
                                                       "counter_ms_p90", "small_ms_p50", "sonnet_calls", "teacher_share")}},
            "months": {k: {"pilot": month(n, p), "cascade": month(n, c, fixed)} for k, n in volumes_.items()},
            "breakeven_docs_per_month": breakeven,
            "counter": {"target_ms": v["counter_target_seconds"] * 1000, "pilot_ms_p50": p["counter_ms_p50"],
                        "cascade_ms_p50": c["counter_ms_p50"], "answered_at_counter": round(1 - c["teacher_share"], 3)}}


def drift(model_name: str | None, threshold: float) -> dict:
    """Homework: the cascade on both keyed sets, and the kinds the small model should be retrained for."""
    out = {}
    rows = []
    for s in ("october", "council_tax"):
        c = cascade(model_name, s, threshold, save=False)
        if c.get("model") is None:
            return {"model": None}
        out[s] = {k: c[k] for k in ("documents", "small_docs", "teacher_docs", "teacher_share", "slipped", "accuracy_after_review", "reasons")}
        out[s]["small_alone"] = evaluate(model_name, s, threshold)["overall"]
        rows += c["rows"]
    try:
        out["candidates"] = retrain_candidates(rows)
        out["built"] = True
    except NotImplementedError:
        out["candidates"], out["built"] = [], False
    out["model"] = get_model(model_name).meta["name"]
    return out


def weights(model_name: str | None, label: str) -> list[dict]:
    m = get_model(model_name)
    return m.weights_for(label) if m else []


def source_of(fn) -> str:
    return inspect.getsource(fn)
