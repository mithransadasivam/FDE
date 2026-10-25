"""Score incidents against data/scenarios.csv: grouping, root cause, severity, status, runbook step, action, approvals, similar, flags."""
from __future__ import annotations

import csv
from pathlib import Path

from .models import Incident
from .settings import ROOT

CHECKS_RULES = ["grouping", "root_cause", "severity", "approvals", "similar", "flags"]  # no model involved
CHECKS_MODEL = ["status", "runbook_step"]  # depends on the model's recommendation
ALL_CHECKS = ["grouping", "root_cause", "severity", "status", "runbook_step", "approvals", "similar", "flags"]


def load_scenarios(path: Path | None = None) -> list[dict]:
    with open(path or ROOT / "data" / "scenarios.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _split(v: str) -> list[str]:
    return [x for x in v.split(";") if x]


def score(incidents: list[Incident], scenarios: list[dict] | None = None) -> dict:
    scenarios = scenarios or load_scenarios()
    rows = []
    for sc in scenarios:
        want_alerts = set(_split(sc["alert_ids"]))
        inc = next((i for i in incidents if set(i.alert_ids) == want_alerts), None)
        mine = next((i for i in incidents if want_alerts & set(i.alert_ids)), None)
        r = {"scenario": sc["scenario"], "incident": inc.incident_id if inc else (mine.incident_id if mine else None)}
        r["grouping"] = inc is not None
        i = inc or mine
        if i is None:
            rows.append({**r, **{c: False for c in ALL_CHECKS if c != "grouping"}})
            continue
        r["root_cause"] = (i.root_cause or "") == sc["root_cause_service"]
        r["severity"] = (i.severity or "") == sc["severity"]
        r["status"] = i.status == sc["status"]
        r["runbook_step"] = ((i.runbook_id or "") == sc["runbook"] and str(i.recommended_step or "") == sc["recommended_step"]
                             and (i.action or "none") == sc["action"] and (i.target or "") == sc["target"])
        r["approvals"] = (i.approvals_needed == int(sc["approvals_needed"])
                          and {a.team for a in i.approvers} == set(_split(sc["approvers"]))
                          and (len({a.engineer for a in i.approvers}) == len(i.approvers)))
        r["similar"] = (i.similar_incident or "") == sc["similar_incident"]
        r["flags"] = set(_split(sc["flags"])) <= set(i.flags)
        r["got"] = {"root_cause": i.root_cause, "severity": i.severity, "status": i.status, "runbook": i.runbook_id,
                    "step": i.recommended_step, "action": i.action, "target": i.target, "approvals": i.approvals_needed,
                    "approvers": [a.team for a in i.approvers], "similar": i.similar_incident, "flags": i.flags}
        r["want"] = {"root_cause": sc["root_cause_service"], "severity": sc["severity"], "status": sc["status"],
                     "runbook": sc["runbook"], "step": sc["recommended_step"], "action": sc["action"], "target": sc["target"],
                     "approvals": sc["approvals_needed"], "approvers": _split(sc["approvers"]), "similar": sc["similar_incident"],
                     "flags": _split(sc["flags"])}
        rows.append(r)
    n = len(rows)
    summary = {c: sum(1 for r in rows if r.get(c)) for c in ALL_CHECKS}
    summary["incident_count"] = len(incidents)
    summary["scenarios"] = n
    return {"rows": rows, "summary": summary}
