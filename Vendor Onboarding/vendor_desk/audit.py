"""The audit trail (Phase 11): one file per case, every handoff, tool call, state change and human decision, with the
time, who did it and a short detail. Nothing private goes in (text is redacted on the way in), and the file is
tamper-evident: each line carries the hash of the line before it, so editing or deleting a line is detected by verify().

runs/team/<case_id>/audit.jsonl
"""
import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from vendor_desk import config
from vendor_desk.safety import redact

GENESIS = "0" * 64
LOCK = threading.RLock()   # parallel specialists write to the same case; one writer at a time


def team_dir() -> Path:
    return config.RUNS_DIR / "team"


def audit_path(case_id: str) -> Path:
    d = team_dir() / case_id
    d.mkdir(parents=True, exist_ok=True)
    return d / "audit.jsonl"


def _hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read(case_id: str) -> list[dict]:
    p = audit_path(case_id)
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def append(case_id: str, who: str, event: str, detail: str, evidence: str = "") -> dict:
    """Add one line. who: 'system', a specialist name, or a person's name. event: e.g. handoff, tool_call, state_change,
    decision, write, draft, reminder."""
    with LOCK:
        return _append(case_id, who, event, detail, evidence)


def _append(case_id: str, who: str, event: str, detail: str, evidence: str) -> dict:
    entries = read(case_id)
    entry = {
        "seq": len(entries) + 1, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "who": who,
        "event": event, "detail": redact(detail)[:400], "evidence": redact(evidence)[:300],
        "prev": entries[-1]["hash"] if entries else GENESIS,
    }
    entry["hash"] = _hash(entry)
    with open(audit_path(case_id), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def verify(case_id: str) -> tuple[bool, str]:
    """(ok, message). Detects an edited, removed or reordered line."""
    prev = GENESIS
    for i, e in enumerate(read(case_id), 1):
        if e["seq"] != i or e["prev"] != prev or e["hash"] != _hash(e):
            return False, f"The audit trail was changed at line {i}."
        prev = e["hash"]
    return True, "The audit trail is intact."
