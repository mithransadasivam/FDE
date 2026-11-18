"""What the Documents screen shows (done: you do not change this file for a ticket).

The two tickets are parse_document() (ENG-601) and route_field() (ENG-602). Everything here calls them.
"""

import csv
import json
import os
from datetime import datetime, timezone
from statistics import mean

from app import store
from app.config import MODEL_PRICES_FILE, PROMPTS_DIR
from app.evaluation.metrics import score_run
from app.llm import llm_client, settings
from app.pipeline import documents as D
from app.pipeline.batch import PROVIDER_LIMIT, Job, run_live, simulate
from app.pipeline.methods import METHODS, method_of, norm, read
from app.pipeline.parse import parse_document
from app.pipeline.routing import OK_AT, route_field
from app.prototype.models import FIELD_LABELS, FIELDS, Field

DOCS_PER_MONTH = 8600  # Day 2: today's volume
GBP_PER_USD = 0.78  # the course's illustrative rate (Day 2 price sheet)
PILOT_MODEL = "anthropic.claude-sonnet-5"  # ADR-002: the pilot's model, in London
CLASS_MODEL = "anthropic/claude-haiku-5.5"  # the price used for scripted runs
OK_GRID = [0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99]


# ---------------------------------------------------------------- prompts, prices, status
def prompts() -> dict:
    names = sorted(p.stem for p in PROMPTS_DIR.glob("extract*.md"))
    return {"parser": [n for n in names if method_of(n) == "parser" and n != "extract"], "vision": [n for n in names if method_of(n) == "vision"]}


def prices() -> list[dict]:
    with open(MODEL_PRICES_FILE, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def price_for(model_id: str) -> dict | None:
    return next((p for p in prices() if p["model_id"] == model_id), None)


def usd(tokens_in: float, tokens_out: float, model_id: str, batch: bool = False) -> float | None:
    p = price_for(model_id)
    if not p:
        return None
    i, o = (p["batch_input_usd_per_m"], p["batch_output_usd_per_m"]) if batch else (p["input_usd_per_m"], p["output_usd_per_m"])
    if batch and not i:  # no batch price listed: assume the usual 50% off, and say so on screen
        i, o = float(p["input_usd_per_m"]) / 2, float(p["output_usd_per_m"]) / 2
    return (tokens_in * float(i) + tokens_out * float(o)) / 1_000_000


def class_model() -> str:
    s = settings()
    return CLASS_MODEL if s["fake"] else s["openrouter_model"]


def status() -> dict:
    s = settings()
    return {"sets": D.sets(), "prompts": prompts(), "fake": s["fake"], "model": class_model(), "prices": prices(),
            "ok_at": OK_AT, "methods": METHODS}


# ---------------------------------------------------------------- Parse tab (ENG-601)
_parsed: dict = {}


def parsed_summary(doc_id: str) -> dict:
    """Source and word counts for one document, kept in memory (the server restarts when parse.py changes)."""
    if doc_id not in _parsed:
        p = parse_document(doc_id)
        confs = [w.confidence for w in p.words]
        _parsed[doc_id] = {"source": p.source, "words": len(p.words), "low_words": sum(c < OK_AT for c in confs),
                           "mean_confidence": round(mean(confs), 3) if confs else 0}
    return _parsed[doc_id]


def documents(set_name: str) -> dict:
    rows, not_built = [], ""
    for r in D.manifest(set_name):
        row = {**r, "slices": [s for s in r["slices"].split(";") if s]}
        if not not_built:
            try:
                row.update(parsed_summary(r["doc_id"]))
            except NotImplementedError as e:
                not_built = str(e)
        rows.append(row)
    counts = {}
    for r in rows:
        k = r["file"].rsplit(".", 1)[1]
        counts[k] = counts.get(k, 0) + 1
    by_source = {}
    for r in rows:
        if "source" in r:
            by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    return {"set": D.get_set(set_name), "documents": rows, "files": counts, "sources": by_source, "not_built": not_built}


def document(doc_id: str) -> dict:
    p = parse_document(doc_id)
    return {"doc_id": doc_id, "file": p.file, "source": p.source, "image": f"/api/pipeline/documents/{doc_id}/image",
            "row": D.doc_row(doc_id), "words": [w.model_dump() for w in p.words]}


# ---------------------------------------------------------------- runs (Compare tab)
def _jobs(set_name: str, prompt_names: list[str], client, skip: dict, force: bool) -> list[Job]:
    jobs, simulated = [], getattr(client, "is_fake", False)
    for r in D.manifest(set_name):
        for p in prompt_names:
            if r["doc_id"] in skip.get(p, {}):
                continue  # already in this run: only the missing documents are read again
            if simulated:
                out = read(r["doc_id"], p, client)  # instant: the scripted reply, with its scripted latency
                jobs.append(Job(key=f"{r['doc_id']}/{p}", run=(lambda out=out: out), latency_ms=out["usage"]["latency_ms"]))
            else:
                jobs.append(Job(key=f"{r['doc_id']}/{p}", run=(lambda d=r["doc_id"], p=p: read(d, p, client, force))))
    return jobs


def run(set_name: str, prompt_names: list[str], concurrency: int = 8, client=None, resume: bool = False, force: bool = False) -> dict:
    """Read every document in the set with each prompt, `concurrency` calls at a time.
    resume=True keeps the documents already in each prompt's run and reads only the missing ones (after a failure).
    force=True asks a real model again instead of using kept replies (to measure real throughput)."""
    client = client or llm_client()
    kept = {p: (load_run(set_name, p) or {}).get("results", {}) if resume else {} for p in prompt_names}
    jobs = _jobs(set_name, prompt_names, client, kept, force)
    if getattr(client, "is_fake", False):
        if os.environ.get("FDE_SMOOTH_BATCH") == "1":  # queue extra calls instead of sending them to be refused
            concurrency = min(concurrency, PROVIDER_LIMIT)
        res = simulate(jobs, concurrency)
    else:
        res = run_live(jobs, concurrency)
    for p in prompt_names:
        results = {**kept[p], **{k.split("/")[0]: v for k, v in res.done.items() if k.endswith("/" + p)}}
        store.save(f"pipeline/runs/{set_name}__{p}.json", {"set": set_name, "prompt": p, "method": method_of(p), "model": class_model(),
                                                           "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "results": results})
    finished_now = {k.split("/")[0] for k in res.done} - {k.split("/")[0] for k in res.failed}
    all_docs = {r["doc_id"] for r in D.manifest(set_name)}
    in_every_run = set.intersection(*[set((load_run(set_name, p) or {"results": {}})["results"]) for p in prompt_names])
    missing = sorted(all_docs - in_every_run)
    return {"calls": len(jobs), "done": len(res.done), "failed": res.failed, "failed_docs": missing, "refusals": res.refusals, "wall_ms": res.wall_ms,
            "simulated": res.simulated, "concurrency": concurrency, "documents": len(all_docs), "complete": len(all_docs) - len(missing),
            "finished_now": len(finished_now), "resume": resume,
            "latency_ms_p50": _pct(res.latencies, 50), "latency_ms_p95": _pct(res.latencies, 95)}


def _pct(xs: list, q: int) -> int:
    if not xs:
        return 0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round((len(xs) - 1) * q / 100))]


def load_run(set_name: str, prompt: str) -> dict | None:
    return store.load(f"pipeline/runs/{set_name}__{prompt}.json", None)


def score(set_name: str, prompt: str) -> dict | None:
    r = load_run(set_name, prompt)
    if not r or not r["results"]:
        return None
    labels, slices = D.labels(set_name), D.slices(set_name)
    outs = {d: {f["name"]: f["value"] for f in v["fields"]} for d, v in r["results"].items()}
    s = score_run(outs, labels, slices)
    fields = [f for v in r["results"].values() for f in v["fields"]]
    n = len(r["results"])
    tin = mean(v["usage"]["input_tokens"] for v in r["results"].values())
    tout = mean(v["usage"]["output_tokens"] for v in r["results"].values())
    cost = usd(tin, tout, r.get("model") or CLASS_MODEL)
    return {"prompt": prompt, "method": r["method"], "model": r.get("model"), "at": r["at"], "documents": n,
            "overall": s.overall.model_dump(), "per_field": {k: v.model_dump() for k, v in s.per_field.items()},
            "per_slice": {k: v.model_dump() for k, v in s.per_slice.items()},
            "grounded": round(100 * sum(f["status"] in ("ok", "check", "doubtful") for f in fields) / len(fields), 1),
            "tokens": {"input": round(tin), "output": round(tout)},
            "latency_ms": round(mean(v["usage"]["latency_ms"] for v in r["results"].values())),
            "scripted": any(v["usage"].get("scripted") for v in r["results"].values()),
            "usd_per_doc": round(cost, 6) if cost is not None else None,
            "errors": [{"doc_id": e.case_id, "field": e.field, "got": e.got, "expected": e.expected} for e in s.errors][:400]}


def human_bar(set_name: str) -> dict:
    """How well the bank's own keyers do: each keyer against the settled label, and the two against each other."""
    k = D.keyed(set_name)
    n = len(k)
    a = sum(norm(r["keyer_a"]) == norm(r["label"]) for r in k)
    b = sum(norm(r["keyer_b"]) == norm(r["label"]) for r in k)
    agree = sum(r["resolved_by"] == "agreed" for r in k)
    return {"fields": n, "keyer_a": round(100 * a / n, 1), "keyer_b": round(100 * b / n, 1), "one_keyer": round(100 * (a + b) / (2 * n), 1),
            "agreement": round(100 * agree / n, 1), "settled_by_tom": n - agree}


def compare(set_name: str) -> dict:
    ps = prompts()
    runs = [s for p in ps["parser"] + ps["vision"] if (s := score(set_name, p))]
    return {"set": set_name, "human": human_bar(set_name), "runs": runs, "prompts": ps}


# ---------------------------------------------------------------- routing and the Review queue (ENG-602)
def _fields(set_name: str, prompt: str) -> dict:
    r = load_run(set_name, prompt) or {"results": {}}
    return {d: {f["name"]: Field(**f) for f in v["fields"]} for d, v in r["results"].items()}


def _actions(set_name: str) -> dict:
    log = store.load(f"pipeline/review_{set_name}.json", {})
    return log


def routed(set_name: str, parser_prompt: str, vision_prompt: str, ok_at: float, use_agreement: bool, apply_reviews: bool = True) -> list[dict]:
    P, V = _fields(set_name, parser_prompt), _fields(set_name, vision_prompt) if vision_prompt else {}
    labels = D.labels(set_name)
    acts = _actions(set_name) if apply_reviews else {}
    out = []
    for d in sorted(P):
        for name in FIELDS:
            pf = P[d][name]
            vf = V.get(d, {}).get(name)
            r = route_field(pf, vf, ok_at, use_agreement)
            act = acts.get(f"{d}/{name}")
            value = act["value"] if act else pf.value
            out.append({"doc_id": d, "field": name, "label": FIELD_LABELS[name], "value": pf.value, "vision": vf.value if vf else None,
                        "confidence": pf.confidence, "status": pf.status, "box": pf.box, "decision": r.decision, "reasons": r.reasons,
                        "correct": norm(pf.value) == norm(labels.get(d, {}).get(name, "")), "expected": labels.get(d, {}).get(name, ""),
                        "reviewed": act, "final": value, "final_correct": norm(value) == norm(labels.get(d, {}).get(name, ""))})
    return out


def routing_settings(set_name: str) -> dict:
    """The routing the team chose last on Pipeline → Routing: the Review queue uses the same."""
    ps = prompts()
    vision = "extract_vlm_v1" if "extract_vlm_v1" in ps["vision"] else (ps["vision"][0] if ps["vision"] else "")
    return store.load(f"pipeline/routing_{set_name}.json", {"parser_prompt": "extract_v2", "vision_prompt": vision, "ok_at": OK_AT, "use_agreement": True})


def routing(set_name: str, parser_prompt: str, vision_prompt: str, ok_at: float = OK_AT, use_agreement: bool = True) -> dict:
    store.save(f"pipeline/routing_{set_name}.json", {"parser_prompt": parser_prompt, "vision_prompt": vision_prompt, "ok_at": ok_at, "use_agreement": use_agreement})
    items = routed(set_name, parser_prompt, vision_prompt, ok_at, use_agreement, apply_reviews=False)
    if not items:
        return {"items": 0}

    def stats(rows):
        n = len(rows)
        review = [r for r in rows if r["decision"] == "review"]
        slipped = [r for r in rows if r["decision"] == "auto" and not r["correct"]]
        caught = [r for r in review if not r["correct"]]
        return {"fields": n, "review": len(review), "review_pct": round(100 * len(review) / n, 1), "slipped": len(slipped),
                "caught": len(caught), "errors": sum(not r["correct"] for r in rows),
                "accuracy_after_review": round(100 * (n - len(slipped)) / n, 1)}

    curve = []
    for agree in ([False, True] if vision_prompt else [False]):
        for t in OK_GRID:
            s = stats(routed(set_name, parser_prompt, vision_prompt, t, agree, apply_reviews=False))
            curve.append({"ok_at": t, "agreement": agree, **s})
    now = stats(items)
    slipped = [r for r in items if r["decision"] == "auto" and not r["correct"]]
    return {"set": set_name, "parser_prompt": parser_prompt, "vision_prompt": vision_prompt, "ok_at": ok_at, "use_agreement": use_agreement,
            **now, "curve": curve, "human": human_bar(set_name), "slipped_items": slipped[:50],
            "reasons": _reason_counts([r for r in items if r["decision"] == "review"])}


def _reason_counts(rows):
    out = {"confidence": 0, "not_on_page": 0, "disagree": 0}
    for r in rows:
        for why in r["reasons"]:
            k = "confidence" if why.startswith("OCR confidence") else "disagree" if why.startswith("The vision model") else "not_on_page"
            out[k] += 1
    return out


def queue(set_name: str) -> dict:
    """The fields the KYC analysts must check, with the routing chosen on Pipeline → Routing."""
    cfg = routing_settings(set_name)
    if not load_run(set_name, cfg["parser_prompt"]):
        return {"items": [], "open": 0, "done": 0, "settings": cfg, "empty": f"No run of {cfg['parser_prompt']} yet: run it on Pipeline → Compare"}
    items = [r for r in routed(set_name, cfg["parser_prompt"], cfg["vision_prompt"], cfg["ok_at"], cfg["use_agreement"]) if r["decision"] == "review"]
    for r in items:
        r.pop("correct"), r.pop("expected"), r.pop("final_correct")  # the analyst does not see the answer
    done = sum(1 for r in items if r["reviewed"])
    return {"items": items, "open": len(items) - done, "done": done, "settings": cfg}


def review(set_name: str, doc_id: str, field: str, action: str, value: str, analyst_id: str) -> dict:
    log = _actions(set_name)
    entry = {"action": action, "value": value, "analyst_id": analyst_id, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    log[f"{doc_id}/{field}"] = entry
    store.save(f"pipeline/review_{set_name}.json", log)
    return entry


# ---------------------------------------------------------------- the batch run (Batch tab)
def batch(set_name: str, parser_prompt: str, vision_prompt: str, concurrency: int = 8, ok_at: float = OK_AT, use_agreement: bool = True,
          resume: bool = False) -> dict:
    """The whole pipeline on the whole set: read with both prompts, route every field, and report.
    resume=True reads only the documents the last batch could not finish."""
    prompt_names = [parser_prompt] + ([vision_prompt] if vision_prompt else [])
    r = run(set_name, prompt_names, concurrency, resume=resume, force=not resume)
    rt = routing(set_name, parser_prompt, vision_prompt, ok_at, use_agreement)
    sp, sv = score(set_name, parser_prompt), score(set_name, vision_prompt) if vision_prompt else None
    tin = sum(s["tokens"]["input"] for s in [sp, sv] if s)
    tout = sum(s["tokens"]["output"] for s in [sp, sv] if s)
    minutes = r["wall_ms"] / 60000 or 1
    month_fields = DOCS_PER_MONTH * len(FIELDS)
    checked = round(month_fields * rt.get("review_pct", 0) / 100)

    def cost(model, batch_price=False):
        c = usd(tin, tout, model, batch_price)
        return None if c is None else {"usd_per_doc": round(c, 5), "gbp_per_month": round(c * DOCS_PER_MONTH * GBP_PER_USD)}

    report = {
        "set": set_name, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "parser_prompt": parser_prompt,
        "vision_prompt": vision_prompt, "concurrency": concurrency, "ok_at": ok_at, "use_agreement": use_agreement,
        "run": r, "throughput_docs_per_min": round(r["finished_now"] / minutes, 1),
        "month_minutes": round(DOCS_PER_MONTH / (r["finished_now"] / minutes)) if r["finished_now"] and not resume else None,
        "accuracy": {"parser": sp["overall"]["accuracy"] if sp else None, "vision": sv["overall"]["accuracy"] if sv else None,
                     "after_review": rt.get("accuracy_after_review"), "one_keyer": human_bar(set_name)["one_keyer"]},
        "routing": {k: rt.get(k) for k in ["fields", "review", "review_pct", "slipped", "caught", "errors"]},
        "tokens_per_doc": {"input": tin, "output": tout},
        "cost": {"class": {"model": class_model(), **(cost(class_model()) or {})},
                 "pilot": {"model": PILOT_MODEL, **(cost(PILOT_MODEL) or {})},
                 "pilot_batch": {"model": PILOT_MODEL, **(cost(PILOT_MODEL, True) or {}),
                                 "note": "50% off, results within 24 hours: check batch inference for this model in eu-west-2"}},
        "fields_per_month": {"typed_today": month_fields, "checked_with_pipeline": checked, "straight_through": month_fields - checked},
        "docs_per_month": DOCS_PER_MONTH, "gbp_per_usd": GBP_PER_USD,
    }
    store.save(f"pipeline/batch_report_{set_name}.json", report)
    hist = store.load(f"pipeline/batch_history_{set_name}.json", [])
    hist.append({"at": report["at"], "concurrency": concurrency, "resume": resume, "calls": r["calls"], "complete": r["finished_now"],
                 "failed_docs": len(r["failed_docs"]), "refusals": r["refusals"], "wall_ms": r["wall_ms"],
                 "docs_per_min": report["throughput_docs_per_min"], "simulated": r["simulated"]})
    store.save(f"pipeline/batch_history_{set_name}.json", hist[-12:])
    report["history"] = hist[-12:]
    return report


def last_batch(set_name: str) -> dict | None:
    r = store.load(f"pipeline/batch_report_{set_name}.json", None)
    if r:
        r["history"] = store.load(f"pipeline/batch_history_{set_name}.json", [])
    return r
