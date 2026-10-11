"""Thumbs up / thumbs down on an answer, saved so the wrong ones can be reviewed and turned into new test cases.

What is saved (one JSON line per rating in logs/feedback.jsonl): the time, the rating, a reason picked from a fixed list, how the
chatbot behaved (answered, declined or refused), the best search score, how many chunks it used and which FILES it cited.
It never saves the answer. It saves the question only when the person ticks the box to include it (default off), shortened and
cleaned, because a question can hold personal details. Like the call log, it never breaks the chatbot: a problem writing is ignored.
"""
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.config import ROOT

FEEDBACK_PATH = ROOT / "logs" / "feedback.jsonl"
ENABLED = os.getenv("FEEDBACK_LOG", os.getenv("CALL_LOG", "1")) != "0"  # FEEDBACK_LOG=0 (or CALL_LOG=0) switches it off
RATINGS = ("up", "down")
REASONS = ("The answer is wrong", "It missed something", "Wrong source", "Should have answered", "Should have declined", "Other")
MAX_QUESTION_CHARS_SAVED = 300
MAX_SOURCES_SAVED = 6


class FeedbackError(ValueError):
    """The rating cannot be saved. The message is friendly and safe to show."""


def clean_question(text: str) -> str:
    """The question as one clean line, no control characters, never longer than the limit."""
    return " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", text or "").split())[:MAX_QUESTION_CHARS_SAVED]


def build_entry(rating: str, outcome: str, best_score, chunks_used, sources, reason: str = "", question: str = "", include_question: bool = False) -> dict:
    """Check the rating and make the record. Raises FeedbackError for a rating or reason that is not on the lists."""
    if rating not in RATINGS:
        raise FeedbackError("Please choose thumbs up or thumbs down.")
    if reason and (rating != "down" or reason not in REASONS):
        raise FeedbackError("That reason is not one of the choices.")
    entry = {
        "rating": rating,
        "reason": reason,
        "outcome": outcome if outcome in ("answered", "declined", "refused") else "answered",
        "best_score": round(float(best_score), 3) if isinstance(best_score, (int, float)) else None,
        "chunks_used": int(chunks_used) if isinstance(chunks_used, int) else 0,
        "sources": sorted({str(s)[:80] for s in (sources or [])})[:MAX_SOURCES_SAVED],
    }
    if include_question and clean_question(question):
        entry["question"] = clean_question(question)
    return entry


def record_feedback(rating: str, outcome: str, best_score, chunks_used, sources, reason: str = "", question: str = "",
                    include_question: bool = False, path: Path | None = None) -> dict:
    """Validate and save one rating. Returns the saved record. Raises FeedbackError for a bad rating; a write problem is ignored."""
    entry = build_entry(rating, outcome, best_score, chunks_used, sources, reason, question, include_question)
    if path is None and not ENABLED:
        return entry
    record = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry}
    target = Path(path) if path else FEEDBACK_PATH
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return record


def read_feedback(path: Path | None = None) -> list[dict]:
    """The saved ratings, oldest first. Unreadable lines are skipped."""
    rows = []
    try:
        with open(Path(path) if path else FEEDBACK_PATH, encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("rating") in RATINGS:
                    rows.append(row)
    except OSError:
        pass
    return rows


def summarize(rows: list[dict]) -> dict:
    """Counts for the review screen: up, down, the share that is down, why, which outcome and which files get the most thumbs down."""
    down = [r for r in rows if r["rating"] == "down"]
    return {
        "total": len(rows),
        "up": len(rows) - len(down),
        "down": len(down),
        "down_rate": round(len(down) / len(rows), 3) if rows else None,
        "by_reason": dict(Counter(r.get("reason") or "(no reason given)" for r in down)),
        "by_outcome": dict(Counter(r.get("outcome", "answered") for r in down)),
        "files": Counter(s for r in down for s in r.get("sources", [])).most_common(5),
        "with_question": sum(1 for r in down if r.get("question")),
    }


def to_csv(rows: list[dict]) -> str:
    """The thumbs-down rows as CSV, ready to turn into test cases. A cell that starts with = + - @ is neutralised against spreadsheet formulas."""
    import csv
    import io
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["time", "reason", "outcome", "best_score", "sources", "question"])
    for r in rows:
        if r["rating"] != "down":
            continue
        cells = [r.get("time", ""), r.get("reason", ""), r.get("outcome", ""), r.get("best_score", ""), "; ".join(r.get("sources", [])), r.get("question", "")]
        writer.writerow([("'" + str(c)) if str(c)[:1] in ("=", "+", "-", "@") else c for c in cells])
    return out.getvalue()
