"""Cases for the UC1 prototype: read a document, ground its fields, apply the rules, log what the analyst does.

Done: you do not change this file for a ticket. The two pieces it calls are the tickets:
ground_fields() (ENG-301) and check_policy() (ENG-302).
"""

import csv
import json
import os
from datetime import datetime, timezone

from app import store
from app.config import APPLICATIONS_FILE, DOCUMENTS_DIR, DOCUMENTS_DIR_4, PROBES_FILE, PROMPTS_DIR, SYNTHETIC_DIR
from app.llm import ask_json
from app.prototype.grounding import ground_fields
from app.prototype.models import FIELD_LABELS, Application, ExtractionReply, Field, OcrWord
from app.prototype.rules import check_policy, load_rules

def load_prompt(name: str) -> str:
    """The extraction prompt, from backend/app/prototype/prompts/<name>.md. "extract" is the Day 3 prompt."""
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def applications() -> dict[str, Application]:
    with open(APPLICATIONS_FILE, encoding="utf-8") as f:
        return {r["case_id"]: Application(**r) for r in csv.DictReader(f)}


def document_dir(case_id: str):
    """Day 3's 30 documents, or Day 4's 20 harder ones (D04-…)."""
    return DOCUMENTS_DIR_4 if case_id.startswith("D04-") else DOCUMENTS_DIR


def ocr_words(case_id: str) -> list[OcrWord]:
    if case_id.startswith("P-"):  # a guardrail probe (Day 5): words only, no image
        probe = next(p for p in json.loads(PROBES_FILE.read_text(encoding="utf-8")) if p["case_id"] == case_id)
        return [OcrWord(**w) for w in probe["words"]]
    if case_id.startswith("S-"):  # a synthetic case (Day 4): words only, no image
        data = json.loads((SYNTHETIC_DIR / f"{case_id}.json").read_text(encoding="utf-8"))
        return [OcrWord(**w) for w in data["words"]]
    data = json.loads((document_dir(case_id) / f"{case_id}.ocr.json").read_text(encoding="utf-8"))
    return [OcrWord(**w) for w in data["words"]]


def read_document(case_id: str, client, prompt: str | None = None) -> ExtractionReply:
    """Ask the model for the fields, once per document and prompt; the reply is kept in engagement/extractions/<prompt>/.
    The prompt is the one named in engagement/poa_rules.json ("prompt"), unless you pass one."""
    prompt = prompt or load_rules().get("prompt", "extract")
    tag = getattr(client, "cache_tag", "")  # Day 5: a different model or guardrail gets its own cache
    folder = f"extractions/{prompt}" + (f"/{tag}" if tag else "")
    cached = store.load(f"{folder}/{case_id}.json", None)
    if cached is not None:
        return ExtractionReply(**cached)
    words = ocr_words(case_id)
    lines = "\n".join(f"{w.id} | {w.text}" for w in words)
    reply = ask_json(client, load_prompt(prompt), f"Document {case_id}. OCR words:\n{lines}", ExtractionReply, task=f"{prompt}/{case_id}")
    store.save(f"{folder}/{case_id}.json", reply.model_dump())
    return reply


def is_read(case_id: str) -> bool:
    prompt = load_rules().get("prompt", "extract")
    return os.getenv("FDE_FAKE_LLM") == "1" or store.path(f"extractions/{prompt}/{case_id}.json").exists()


def _log(name: str) -> list[dict]:
    p = store.path(name)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append(name: str, entry: dict) -> dict:
    entry = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry}
    with open(store.path(name), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def field_actions(case_id: str) -> list[dict]:
    return [e for e in _log("field_log.jsonl") if e["case_id"] == case_id]


def decisions(case_id: str | None = None) -> list[dict]:
    return [e for e in _log("decision_log.jsonl") if case_id is None or e["case_id"] == case_id]


def log_field(case_id: str, name: str, action: str, value: str, analyst_id: str, was: str) -> dict:
    return _append("field_log.jsonl", {"case_id": case_id, "field": name, "action": action, "value": value,
                                       "was": was, "analyst_id": analyst_id})


def log_decision(case_id: str, decision: str, analyst_id: str, reason: str) -> dict:
    return _append("decision_log.jsonl", {"case_id": case_id, "decision": decision, "analyst_id": analyst_id, "reason": reason})


def apply_actions(fields: list[Field], actions: list[dict]) -> list[Field]:
    """A person's accept or correct makes a field "confirmed", with the value they chose."""
    latest = {a["field"]: a for a in actions}
    out = []
    for f in fields:
        a = latest.get(f.name)
        if a:
            note = "Accepted by the analyst" if a["action"] == "accept" else f"Corrected by the analyst (was {a['was'] or 'empty'})"
            f = f.model_copy(update={"value": a["value"], "status": "confirmed", "note": note})
        out.append(f)
    return out


def recommendation(checks) -> str:
    """ready: every check passes · fails: at least one fails · look: a person must confirm a field first."""
    st = {c.status for c in checks}
    if "fail" in st:
        return "fails"
    if "look" in st:
        return "look"
    return "ready"


def case_view(case_id: str, client, strict: bool = True) -> dict:
    """Everything the review screen needs. With strict=False, a ticket that is not built yet leaves
    fields or checks as None (listed in not_built) instead of failing, so the screen still opens."""
    app = applications()[case_id]
    rules = load_rules()
    fields = checks = None
    not_built: list[str] = []
    reply = read_document(case_id, client)
    try:
        fields = ground_fields(reply, ocr_words(case_id), rules["ok_at"], rules["check_at"])
        fields = apply_actions(fields, field_actions(case_id))
        checks = check_policy({f.name: f for f in fields}, app, rules)
    except NotImplementedError as e:
        if strict:
            raise
        not_built.append(str(e))
    done = decisions(case_id)
    return {
        "application": app.model_dump(),
        "document": {"image": f"/api/cases/{case_id}/image", "file": app.document},
        "fields": [f.model_dump() for f in fields] if fields is not None else None,
        "checks": [c.model_dump() for c in checks] if checks is not None else None,
        "recommendation": recommendation(checks) if checks is not None else None,
        "decision": done[-1] if done else None,
        "labels": FIELD_LABELS,
        "not_built": not_built,
    }
