"""The quality gate: compare the latest evaluation numbers with the limits in data/eval_thresholds.json.

One verdict per dimension (PASS, FAIL or UNTESTED when its numbers are missing) and one overall verdict.
The gate is plain code: no model, no network. Run it with `python -m scripts.gate`; it exits 1 unless every dimension passes.
"""
import json
import operator
from pathlib import Path

from app.config import ROOT
from app.eval_suite import DIMENSIONS, RESULTS_JSON, SUMMARY_JSON

THRESHOLDS_JSON = ROOT / "data" / "eval_thresholds.json"
HISTORY_JSONL = ROOT / "data" / "eval_history.jsonl"
OPERATORS = {">=": operator.ge, "<=": operator.le, "==": operator.eq, ">": operator.gt, "<": operator.lt}


class GateError(ValueError):
    """The thresholds file is missing or malformed."""


def load_thresholds(path: Path = THRESHOLDS_JSON) -> dict:
    """The limits per dimension. Raises GateError when the file is unreadable or a check is malformed."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise GateError(f"The thresholds file could not be read ({type(err).__name__}).") from err
    if not isinstance(data, dict):
        raise GateError("The thresholds file must be a JSON object.")
    for dimension in DIMENSIONS:
        entry = data.get(dimension)
        if not isinstance(entry, dict) or not entry.get("checks"):
            raise GateError(f"The thresholds file has no checks for '{dimension}'.")
        for check in entry["checks"]:
            if not (isinstance(check, list) and len(check) == 3 and check[1] in OPERATORS):
                raise GateError(f"A check for '{dimension}' is not [metric, operator, limit]: {check!r}.")
    return data


def load_summary(path: Path = SUMMARY_JSON) -> dict:
    """The latest evaluation numbers, or {} when there are none yet."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def metrics_for(summary: dict, dimension: str) -> dict:
    """The numbers the checks for one dimension read. Performance is the entry for the mode the run used."""
    if dimension == "performance":
        mode = (summary.get("run") or {}).get("mode")
        return (summary.get("performance") or {}).get(mode) or {}
    return summary.get(dimension) or {}


def evaluate(summary: dict, thresholds: dict) -> dict:
    """Check every dimension.

    Returns {"dimensions": {name: {label, status, checks: [{metric, op, limit, value, passed}], why}}, "passing", "total", "ready"}.
    A dimension is UNTESTED when a number it needs is missing, and that stops the gate like a FAIL does.
    """
    out = {}
    for dimension in DIMENSIONS:
        spec, numbers = thresholds[dimension], metrics_for(summary, dimension)
        checks, status = [], "PASS"
        for metric, op, limit in spec["checks"]:
            value = numbers.get(metric)
            passed = value is not None and OPERATORS[op](value, limit)
            checks.append({"metric": metric, "op": op, "limit": limit, "value": value, "passed": passed})
            if value is None:
                status = "UNTESTED" if status == "PASS" else status
            elif not passed:
                status = "FAIL"
        out[dimension] = {"label": spec.get("label", dimension), "status": status, "checks": checks, "why": spec.get("why", "")}
    passing = sum(1 for d in out.values() if d["status"] == "PASS")
    return {"dimensions": out, "passing": passing, "total": len(out), "ready": passing == len(out)}


def failed_cases(path: Path = RESULTS_JSON) -> list[dict]:
    """The cases of the last full run that did not pass: {id, dimension, input, why}. Empty when there is no run."""
    try:
        rows = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [{"id": r["id"], "dimension": r["dimension"], "input": r["input"][:120].replace("\n", " "),
             "why": "; ".join(r["failed"]) or r.get("error", "")} for r in rows if not r.get("passed")]


def record_history(label: str, mode: str, verdict: dict, path: Path = HISTORY_JSONL) -> None:
    """Append this verdict to the run history (one JSON line per gate run)."""
    from datetime import datetime, timezone
    entry = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "label": label, "mode": mode,
             "passing": verdict["passing"], "total": verdict["total"], "ready": verdict["ready"],
             "failing": [d for d, v in verdict["dimensions"].items() if v["status"] != "PASS"]}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def load_history(path: Path = HISTORY_JSONL) -> list[dict]:
    """Earlier gate runs, oldest first. Unreadable lines are skipped."""
    rows = []
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        pass
    return rows


def headline(dimension: str, status_entry: dict) -> str:
    """The one number shown on a dimension's card."""
    first = status_entry["checks"][0]
    value = first["value"]
    if value is None:
        return "no data"
    if first["metric"] in ("pass_rate", "correct", "faithfulness", "answer_relevance", "context_recall", "context_precision", "ticket_field_accuracy", "screenshot_pass_rate", "voice_answered", "scan_answered", "injection_resisted"):
        return f"{value:.0%}"
    if first["metric"].endswith("seconds"):
        return f"{value:.1f} s"
    return str(value)
