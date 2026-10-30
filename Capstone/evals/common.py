"""Shared by every Day 4 evaluation: where reports go and how they are written.

Every report is written by code, never by hand, into reports/<name>.json and reports/<name>.md with the date, the models and settings it ran with,
the results and a pass or fail. The governance pack (scripts/governance_pack.py) reads these files and refuses reports that are missing or too old.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings

REPORTS = Path("reports")
MAX_AGE_DAYS = 7


def run_info() -> dict:
    s = get_settings()
    return {"mode": "fake models (simulated)" if s.fake_models else "real models",
            "models": {"llm": s.llm_model, "large": s.large_model, "small": s.small_model, "local": s.local_model, "vision": s.vision_model, "whisper": s.whisper_model},
            "guardrails_enabled": getattr(s, "guardrails_enabled", True)}


def write_report(name: str, title: str, settings: dict, results: dict, passed: bool, md_body: str, extra: dict | None = None) -> dict:
    REPORTS.mkdir(exist_ok=True)
    doc = {"report": name, "title": title, "date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "run": run_info(), "settings": settings,
           "results": results, "passed": bool(passed), **(extra or {})}
    (REPORTS / f"{name}.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    verdict = "PASS" if passed else "FAIL"
    head = (f"# {title}\n\n**Result: {verdict}**  \nDate: {doc['date']}  \nRun: {doc['run']['mode']}; models: {doc['run']['models']['llm']}  \n"
            f"Settings: {json.dumps(settings, default=str)}\n\n")
    (REPORTS / f"{name}.md").write_text(head + md_body.strip() + "\n", encoding="utf-8")
    return doc


def load_report(name: str) -> dict | None:
    p = REPORTS / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def age_days(doc: dict) -> float:
    return (datetime.now(timezone.utc) - datetime.fromisoformat(doc["date"])).total_seconds() / 86400


def table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
    return "\n".join(out)
