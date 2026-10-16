"""Case notes (Phase 4): what is known about a case, with the source of every finding, saved per case id so a vendor's
reply continues the case instead of starting again (the idea of Day 12's notebook).

runs/<engine>/<case_id>/notes.json   findings, facts, flags, decision, draft email, history
runs/<engine>/<case_id>/trace-N.jsonl  one trace file per run
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from vendor_desk import config


def case_id_for(request_id: str) -> str:
    m = re.match(r"^REQ-(\d{3})", request_id)
    if not m:
        raise ValueError(f"'{request_id}' is not a request id")
    return f"VOB-{m.group(1)}"


def case_dir(engine: str, case_id: str) -> Path:
    d = config.RUNS_DIR / engine / case_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_notes(engine: str, case_id: str) -> dict | None:
    p = config.RUNS_DIR / engine / case_id / "notes.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def save_notes(engine: str, case_id: str, notes: dict) -> None:
    (case_dir(engine, case_id) / "notes.json").write_text(json.dumps(notes, indent=2, ensure_ascii=False), encoding="utf-8")


def save_trace(engine: str, case_id: str, run) -> Path:
    d = case_dir(engine, case_id)
    n = len(list(d.glob("trace-*.jsonl"))) + 1
    path = d / f"trace-{n}.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for e in run.trace:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return path


def update_notes(engine: str, case_id: str, run, notes: dict | None = None, draft: dict | None = None) -> dict:
    """Merge one run into the case notes. Findings from checks this run actually executed get this request as their
    source; findings that were only reused keep their earlier source."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    notes = notes or load_notes(engine, case_id) or {
        "case_id": case_id, "vendor_name": None, "request_ids": [], "facts": {}, "findings": {}, "flags": [],
        "decision": None, "missing_items": [], "draft_email": None, "history": []}
    if run.request_id not in notes["request_ids"]:
        notes["request_ids"] = list(dict.fromkeys(run.thread + [run.request_id]))
    facts = notes["facts"]
    executed = {}
    for tr in run.tool_results:
        r, a = tr["result"], tr["args"]
        if "error" in r:
            continue
        if r.get("check"):
            executed[r["check"]] = r
        if tr["name"] == "check_payment_terms":
            facts["terms_days"] = a.get("days")
        elif tr["name"] == "check_spend_threshold":
            facts["amount_gbp"], facts["period"] = a.get("amount_gbp"), a.get("period")
        elif tr["name"] == "check_documents":
            for k in ("legal_name", "tax_id", "registered_country"):
                if r.get(k):
                    facts[k] = r[k]
    a = run.assessment
    if a:
        notes["vendor_name"] = a["vendor_name"]
        for c in a["checks"]:
            raw = executed.get(c["check"])
            if raw is not None:
                notes["findings"][c["check"]] = {**c, "source": run.request_id, "at": now, "data": raw}
            elif c["check"] not in notes["findings"]:
                notes["findings"][c["check"]] = {**c, "source": run.request_id, "at": now, "data": {}}
        notes["flags"], notes["decision"] = a["flags"], a["recommended_decision"]
        notes["missing_items"] = a["missing_items"]
        notes["history"].append({"at": now, "request_id": run.request_id, "status": run.status,
                                 "decision": a["recommended_decision"], "tool_calls": run.usage.tool_calls})
    else:
        notes["history"].append({"at": now, "request_id": run.request_id, "status": run.status, "decision": None,
                                 "tool_calls": run.usage.tool_calls})
    if draft is not None:
        notes["draft_email"] = draft
    save_notes(engine, case_id, notes)
    return notes
