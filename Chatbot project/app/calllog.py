"""A log of every chatbot call: when, which mode, how long, how many tokens, and whether it failed.

One JSON object per line in logs/calls.jsonl. It never records the question or the answer, only the numbers, so
it holds nothing personal. Tests switch it off (see tests/conftest.py).
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.config import ROOT

LOG_PATH = ROOT / "logs" / "calls.jsonl"
ENABLED = os.getenv("CALL_LOG", "1") != "0"  # set CALL_LOG=0 to switch the log off


def outcome_of(result: dict) -> str:
    """One word for what the chatbot did: refused, declined, asked, or answered."""
    if result.get("refused"):
        return "refused"
    if result.get("declined"):
        return "declined"
    if result.get("chunks_used", 0) == 0 and not result.get("sources"):
        return "asked"
    return "answered"


def log_call(entry: dict, path: Path | None = None) -> None:
    """Append one call to the log. Logging must never break the chatbot, so any problem is swallowed."""
    if path is None and not ENABLED:
        return
    target = Path(path) if path else LOG_PATH
    record = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry}
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def read_log(path: Path | None = None) -> list[dict]:
    """The logged calls, oldest first. Unreadable lines are skipped."""
    rows = []
    try:
        with open(Path(path) if path else LOG_PATH, encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return rows
