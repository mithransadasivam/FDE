"""Cost and speed numbers (Day 4, prompt 5), read from the ModelCall log and the ResponseTiming log. Nothing here is estimated by hand:
the Trust and cost page and scripts/cost_report.py both call these functions, so they always show the same numbers.
"""
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.db import OpsSession, init_ops_db
from app.models_ext import ModelCall, ResponseTiming

REPORTS = Path("reports")
STEPS = ("transcription", "scoring", "question", "diagram", "speech")
CV_READ = ("document",)
CV_SCREEN = ("screening", "checker")
INTERVIEW = ("interviewer", "diagrams", "scorecard")
COPILOT = ("copilot",)


def _per(calls: list, agents: tuple, key=lambda c: c.candidate_id) -> dict:
    rows = [c for c in calls if c.agent in agents]
    units = {key(c) for c in rows if key(c) is not None}
    cost = sum(c.cost_usd for c in rows)
    return {"cost": round(cost, 6), "units": len(units), "per_unit": round(cost / len(units), 6) if units else None, "calls": len(rows)}


def cost_numbers() -> dict:
    init_ops_db()  # a database made before a table was added gets it now (create_all only adds what is missing)
    with OpsSession() as ops:
        calls = list(ops.scalars(select(ModelCall)))
    read, screen, interview, copilot = _per(calls, CV_READ), _per(calls, CV_SCREEN), _per(calls, INTERVIEW), _per(calls, COPILOT)
    per_cv = None
    if read["per_unit"] is not None or screen["per_unit"] is not None:
        per_cv = (read["per_unit"] or 0.0) + (screen["per_unit"] or 0.0)
    by_agent: dict[str, dict] = {}
    for c in calls:
        a = by_agent.setdefault(c.agent or "?", {"calls": 0, "cost": 0.0, "tokens": 0, "cached": 0, "seconds": 0.0})
        a["calls"] += 1
        a["cost"] += c.cost_usd
        a["tokens"] += c.tokens_in + c.tokens_out
        a["cached"] += 1 if c.cached else 0
        a["seconds"] += (c.latency_ms or 0.0) / 1000
    for a in by_agent.values():
        a["cost"], a["seconds"] = round(a["cost"], 6), round(a["seconds"], 3)
    model_calls = [c for c in calls if c.agent != "voice" and c.agent != "speech"]
    return {"per_cv_read": read, "per_cv_screened": screen, "per_cv": round(per_cv, 6) if per_cv is not None else None,
            "per_100_cvs": round(per_cv * 100, 4) if per_cv is not None else None,
            "per_interview": interview, "per_copilot_session": copilot, "by_agent": dict(sorted(by_agent.items(), key=lambda kv: -kv[1]["cost"])),
            "calls": len(calls), "total_cost": round(sum(c.cost_usd for c in calls), 4),
            "simulated": all(c.simulated for c in model_calls) if model_calls else True,
            "provider_priced": sum(1 for c in model_calls if not c.simulated and c.cost_usd > 0), "free_local_calls": sum(1 for c in calls if c.tier == "local" and c.cost_usd == 0)}


def _pct(values: list[float], p: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, int(round(p * (len(s) - 1))))]


def speed_numbers() -> dict:
    init_ops_db()
    with OpsSession() as ops:
        rows = list(ops.scalars(select(ResponseTiming)))
    if not rows:
        return {"answers": 0, "steps": {}, "total": None, "simulated": True}
    steps = {s: {"median": round(statistics.median(getattr(r, s) for r in rows), 4), "slowest": round(max(getattr(r, s) for r in rows), 4)} for s in STEPS}
    totals = [r.total_s for r in rows]
    slow = max(rows, key=lambda r: r.total_s)
    return {"answers": len(rows), "steps": steps, "simulated": all(r.simulated for r in rows),
            "total": {"median": round(statistics.median(totals), 4), "slowest": round(max(totals), 4), "p95": round(_pct(totals, 0.95), 4)},
            "slowest_step_overall": max(STEPS, key=lambda s: steps[s]["median"]), "slowest_answer": {"candidate": slow.candidate_id, "turn": slow.turn, "total_s": slow.total_s}}


def report(name: str) -> dict | None:
    p = REPORTS / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def latest_reports() -> list[dict]:
    """Identity swap, accent, attack and copilot reports: when they were run and whether they passed (read from reports/, never typed in)."""
    out = []
    for name, label in (("identity_swap", "Identity swap"), ("accent_test", "Accent test"), ("attack_report", "Attack tests"), ("copilot_eval", "Copilot evaluation")):
        r = report(name)
        if r is None:
            out.append({"name": name, "label": label, "status": "not run", "date": None, "age_days": None, "passed": None})
            continue
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(r["date"])).total_seconds() / 86400
        out.append({"name": name, "label": label, "status": "PASS" if r["passed"] else "FAIL", "date": r["date"][:10], "age_days": round(age, 1), "passed": r["passed"],
                    "detail": _detail(name, r)})
    return out


def _detail(name: str, r: dict) -> str:
    res = r.get("results", {})
    if name == "identity_swap":
        return f"largest change in total {res.get('largest_total_change')} points; must-haves dropped {res.get('planned_must_haves_dropped')}"
    if name == "accent_test":
        return f"largest level difference {res.get('largest_level_difference')}; {len(r.get('settings', {}).get('voices', []))} voices"
    if name == "attack_report":
        return f"{res.get('stopped')} of {res.get('total')} attacks stopped"
    if name == "copilot_eval":
        return f"slowest warning {res.get('warning_seconds_slowest')} s; false alarms {sum((res.get('false_alarms') or {}).values())}"
    return ""


def copilot_warning_times() -> dict | None:
    r = report("copilot_eval")
    if r is None:
        return None
    res = r["results"]
    return {"average_s": res.get("warning_seconds_average"), "slowest_s": res.get("warning_seconds_slowest"), "interviews": res.get("interviews"), "date": r["date"][:10]}
