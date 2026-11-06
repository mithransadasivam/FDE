"""Day 4: the evaluation set, runs of the prototype over it, LLM judges and synthetic cases.

Done: you do not change this file for a ticket. It calls the two tickets in metrics.py:
score_run() (ENG-402) and agreement() (ENG-401).
"""

import csv
import json
import os
import random
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

from app import store
from app.config import (APPLICATIONS_FILE, EVAL_APPLICATIONS_FILE, EVAL_LABELS_FILE, JUDGES_DIR, LABELLING_SAMPLE_FILE,
                        SYNTHETIC_DIR, TOM_SAMPLE_LABELS_FILE, TOM_TAGS_FILE)
from app.llm import ask_json
from app.prototype.cases import ocr_words, read_document, recommendation
from app.prototype.grounding import ground_fields
from app.prototype.models import Application
from app.prototype.rules import check_policy, load_rules
from app.evaluation.metrics import FIELDS, agreement, score_run

JUDGES = {  # judge name -> (the field it reads, the failure type it looks for)
    "wrong_date": ("statement_date", "wrong_date_chosen"),
    "incomplete_name": ("full_name", "incomplete_name"),
}


def _csv(path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ the evaluation set
def real_cases() -> dict[str, dict]:
    """The 50 documents Tom checked: Day 3's 30 and Day 4's 20 harder ones."""
    apps = {r["case_id"]: Application(**r) for r in _csv(APPLICATIONS_FILE) + _csv(EVAL_APPLICATIONS_FILE)}
    out = {}
    for r in _csv(EVAL_LABELS_FILE):
        out[r["case_id"]] = {"labels": {f: r[f] for f in FIELDS} | {"tom_decision": r["tom_decision"], "tom_note": r["tom_note"]},
                             "slices": r["slices"].split(";"), "application": apps[r["case_id"]], "synthetic": False}
    return out


def synthetic_cases() -> dict[str, dict]:
    out = {}
    if SYNTHETIC_DIR.exists():
        for p in sorted(SYNTHETIC_DIR.glob("S-*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            out[d["case_id"]] = {"labels": d["labels"], "slices": [d["slice"], "synthetic"],
                                 "application": Application(**d["application"]), "synthetic": True}
    return out


def eval_cases(set_name: str) -> dict[str, dict]:
    if set_name == "real":
        return real_cases()
    if set_name == "synthetic":
        return synthetic_cases()
    return real_cases() | synthetic_cases()


# ------------------------------------------------------------------ runs
def run_set(set_name: str, prompt: str, client) -> dict:
    """Run the prototype (extraction, grounding, rules) over a set, score it against the labels, and save the run."""
    cases = eval_cases(set_name)
    rules = load_rules()
    outputs, decisions, rule_errors = {}, {}, []
    rule_agree = rule_total = 0
    for cid, c in cases.items():
        fields = ground_fields(read_document(cid, client, prompt), ocr_words(cid), rules["ok_at"], rules["check_at"])
        outputs[cid] = {f.name: f.value for f in fields}
        rec = recommendation(check_policy({f.name: f for f in fields}, c["application"], rules))
        decisions[cid] = rec
        if rec != "look":
            rule_total += 1
            tom = c["labels"].get("tom_decision", "approve")
            if (rec == "ready") == (tom == "approve"):
                rule_agree += 1
            else:
                rule_errors.append({"case_id": cid, "field": "decision", "got": "fails a rule" if rec == "fails" else "ready to approve",
                                    "expected": tom.replace("_", " ")})
    score = score_run(outputs, {k: c["labels"] for k, c in cases.items()}, {k: c["slices"] for k, c in cases.items()})
    name = f"{prompt}__{set_name}"
    run = {"name": name, "prompt": prompt, "set": set_name, "at": _now(), "cases": len(cases),
           "score": score.model_dump(), "rules": {"agree": rule_agree, "compared": rule_total, "errors": rule_errors},
           "outputs": outputs, "decisions": decisions}
    store.path("eval/runs").mkdir(parents=True, exist_ok=True)
    store.save(f"eval/runs/{name}.json", run)
    return run


def list_runs() -> list[dict]:
    p = store.path("eval/runs")
    p.mkdir(parents=True, exist_ok=True)
    out = []
    for f in sorted(p.glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        out.append({k: r[k] for k in ("name", "prompt", "set", "at", "cases", "rules")} | {"overall": r["score"]["overall"]})
    return out


# ------------------------------------------------------------------ failure tags and the taxonomy
def taxonomy(tags: dict[str, str]) -> list[dict]:
    """Count each failure type, most frequent first, with the cumulative share: a Pareto table."""
    counts: dict[str, int] = {}
    for t in tags.values():
        if t:
            counts[t] = counts.get(t, 0) + 1
    total = sum(counts.values())
    out, cum = [], 0
    for t, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        cum += n
        out.append({"type": t, "count": n, "share": round(100 * n / total, 1), "cumulative": round(100 * cum / total, 1)})
    return out


def tom_tags() -> list[dict]:
    return _csv(TOM_TAGS_FILE)


# ------------------------------------------------------------------ labelling with the expert
def labelling_items() -> list[dict]:
    return _csv(LABELLING_SAMPLE_FILE)


def tom_sample_labels() -> dict[str, str]:
    return {r["item"]: r["label"] for r in _csv(TOM_SAMPLE_LABELS_FILE)}


def compare_labels(mine: dict[str, str], guideline: str) -> dict:
    a = agreement(mine, tom_sample_labels(), positive="wrong")
    rounds = store.load("eval/label_rounds.json", [])
    rounds.append({"round": len(rounds) + 1, "guideline": guideline, "at": _now(), "agreement": a.model_dump()})
    store.save("eval/label_rounds.json", rounds)
    return {"agreement": a.model_dump(), "rounds": rounds, "tom": tom_sample_labels()}


# ------------------------------------------------------------------ LLM judges
class JudgeVerdict(BaseModel):
    verdict: Literal["pass", "fail"]
    reason: str


def judge_prompts() -> dict[str, list[str]]:
    """{judge name: [prompt file stems]} from evals/judges/, e.g. wrong_date.md and wrong_date_v1.md."""
    out: dict[str, list[str]] = {j: [] for j in JUDGES}
    for p in sorted(JUDGES_DIR.glob("*.md")):
        for j in JUDGES:
            if p.stem == j or p.stem.startswith(j + "_"):
                out[j].append(p.stem)
    return out


def run_judge(stem: str, client) -> dict:
    """Run a judge prompt over the Day 3 prompt's outputs on the 50 real cases, and calibrate it against Tom's tags."""
    judge = next(j for j in JUDGES if stem == j or stem.startswith(j + "_"))
    field, failure = JUDGES[judge]
    system = (JUDGES_DIR / f"{stem}.md").read_text(encoding="utf-8")
    cases = real_cases()
    rules = load_rules()
    expert_fail = {t["case_id"] for t in tom_tags() if t["field"] == field and t["failure_type"] == failure}
    verdicts, rater, expert = {}, {}, {}
    for cid in cases:
        words = ocr_words(cid)
        fields = {f.name: f for f in ground_fields(read_document(cid, client, "extract"), words, rules["ok_at"], rules["check_at"])}
        text = "\n".join(f"{w.id} | {w.text}" for w in words)
        user = f"Document {cid}. OCR words:\n{text}\n\nField: {field}\nValue to judge: {fields[field].value}"
        v = ask_json(client, system, user, JudgeVerdict, task=f"judge/{stem}/{cid}")
        verdicts[cid] = {"verdict": v.verdict, "reason": v.reason, "value": fields[field].value,
                         "expert": "fail" if cid in expert_fail else "pass", "expected": cases[cid]["labels"][field]}
        rater[cid] = v.verdict
        expert[cid] = "fail" if cid in expert_fail else "pass"
    a = agreement(rater, expert, positive="fail")
    result = {"judge": judge, "prompt": stem, "field": field, "failure_type": failure, "at": _now(),
              "agreement": a.model_dump(), "verdicts": verdicts}
    store.path("eval/judges").mkdir(parents=True, exist_ok=True)
    store.save(f"eval/judges/{stem}.json", result)
    return result


# ------------------------------------------------------------------ synthetic edge cases
SLICES = {
    "two_dates": "Utility or council bills that print both a statement (issue) date and a payment due date, with varied labels such as "
                 "'Statement date', 'Date of issue', 'Bill date', 'Issued', 'Payment due', 'Due by', 'Pay by'. In about half, the payment date comes first.",
    "joint_names": "Bills addressed to two people, such as 'Mr A Shah & Mrs P Shah'. The applicant is the first person.",
    "issuer_variant": "Bills where the issuer prints its legal name, such as 'Lumenvale Energy Ltd', 'HARROWGATE WATER' or 'Northmere Bank plc'.",
    "address_order": "Flats where the address is printed as '<number> <street>, Flat <n>' but the application says 'Flat <n>, <number> <street>'.",
}
GEN_SYSTEM = """You write synthetic test documents for a proof-of-address checker. All people, addresses and organisations are fictional.
Issuers must be one of: Lumenvale Energy, Harrowgate Water, Fenwick Gas & Power, Copperline Broadband, Northmere Bank, Brightwell Borough Council
(or their legal-name variants when asked). Postcodes start with GL. Dates are in 2026, written like '12 Sep 2026'.
Return JSON: {"documents": [{"lines": [{"field": "issuer|full_name|address|statement_date|due_date|other", "text": "..."}],
"labels": {"full_name": ..., "address": lines joined with ", ", "statement_date": ..., "issuer": ...},
"application": {"applicant_name": ..., "address_line1": ..., "town": ..., "postcode": ...}}]}.
Put labels such as 'Statement date' on their own line with field "other"."""


class SynLine(BaseModel):
    field: str
    text: str


class SynDoc(BaseModel):
    lines: list[SynLine]
    labels: dict[str, str]
    application: dict[str, str]


class SynBatch(BaseModel):
    documents: list[SynDoc]


def _words(lines: list[SynLine]) -> list[dict]:
    words, wid = [], 0
    for li, ln in enumerate(lines):
        x = 0.07
        for tok in ln.text.split():
            wid += 1
            w = 0.012 * len(tok) + 0.01
            words.append({"id": f"w{wid:03d}", "text": tok, "box": [round(x, 3), round(0.08 + li * 0.04, 3), round(x + w, 3), round(0.105 + li * 0.04, 3)],
                          "confidence": round(random.uniform(0.94, 0.995), 3)})
            x += w + 0.008
    return words


def make_synthetic(slice_name: str, n: int, client) -> list[str]:
    """Write n synthetic cases for one slice to evals/synthetic/ and return their ids.
    With the scripted model, they come from backend/tests/fixtures/synthetic.json."""
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)
    made = []
    if os.getenv("FDE_FAKE_LLM") == "1":
        from app.llm import FIXTURES
        pool = [d for d in json.loads((FIXTURES / "synthetic.json").read_text(encoding="utf-8")) if d["slice"] == slice_name]
        for d in pool[:n]:
            (SYNTHETIC_DIR / f"{d['case_id']}.json").write_text(json.dumps(d, indent=1) + "\n", encoding="utf-8")
            made.append(d["case_id"])
        return made
    batch = ask_json(client, GEN_SYSTEM, f"Write {n} documents. {SLICES[slice_name]}", SynBatch, task=f"synthetic/{slice_name}")
    start = 101 + len(list(SYNTHETIC_DIR.glob("S-*.json")))
    for k, doc in enumerate(batch.documents[:n]):
        cid = f"S-{start + k:03d}"
        app = {"case_id": cid, "application_date": "2026-10-05", "received_date": "2026-10-28", "channel": "synthetic", "document": "",
               "applicant_name": "", "address_line1": "", "town": "", "postcode": ""} | doc.application
        d = {"case_id": cid, "slice": slice_name, "words": _words(doc.lines), "application": app,
             "labels": {**doc.labels, "tom_decision": "approve"}}
        (SYNTHETIC_DIR / f"{cid}.json").write_text(json.dumps(d, indent=1) + "\n", encoding="utf-8")
        made.append(cid)
    return made
