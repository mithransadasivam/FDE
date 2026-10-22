"""Day 15: monitoring. The API writes one line per request to logs/requests.jsonl; summarise() turns
those lines into the numbers on the dashboard (http://localhost:8000/dashboard).

Done: log_request(), read_requests(), estimate_cost() and summarise().
Homework, Task 1: check_alerts() (done). Check it with tests/test_alerts.py.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
REQUEST_LOG = os.getenv("REQUEST_LOG", "logs/requests.jsonl")
ALERT_RULES = os.getenv("ALERT_RULES", "data/Day15_HW_Slide03_alert_rules.json")

# US dollars per million tokens (input and output averaged). Illustrative: check the current
# prices on each model's OpenRouter page and change them here.
PRICES = {
    "anthropic/claude-haiku-4.5": 3.0,
    "openai/gpt-4.1-mini": 1.0,
    "deepseek/deepseek-chat": 0.6,
}


def log_request(log_file: str | None = None, **fields) -> None:
    """Append one request to the log: time, plus the fields given (request_id, status, seconds ...).
    A log that cannot be written is reported, but never stops the answer reaching the user."""
    path = Path(log_file or REQUEST_LOG)
    entry = {
        "time": datetime.now().astimezone().isoformat(timespec="seconds"),
        **fields,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as error:
        print(f"Could not write the request log {path}: {error}", file=sys.stderr)


def read_requests(log_file: str | None = None, last: int = 500) -> list[dict]:
    path = Path(log_file or REQUEST_LOG)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-last:]
    return [json.loads(line) for line in lines if line.strip()]


def estimate_cost(model: str | None, tokens: int | None) -> float:
    return (tokens or 0) * PRICES.get(model or "", 0.0) / 1_000_000


def percentile(values: list[float], p: float) -> float | None:
    """The value below which p percent of the values fall (nearest rank)."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, round(p / 100 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def summarise(records: list[dict]) -> dict:
    """The dashboard numbers for a list of logged requests."""
    ok = [r for r in records if r.get("status") == "ok"]
    seconds = [r["seconds"] for r in ok if r.get("seconds") is not None]
    tokens = sum(r.get("tokens") or 0 for r in ok)
    by_model = {}
    for r in ok:
        by_model[r.get("model")] = by_model.get(r.get("model"), 0) + 1
    n = len(records)
    return {
        "requests": n,
        "errors": n - len(ok),
        "error_rate": round((n - len(ok)) / n, 3) if n else 0.0,
        "p50_seconds": percentile(seconds, 50),
        "p95_seconds": percentile(seconds, 95),
        "fallbacks": sum(1 for r in ok if r.get("fallback")),
        "declined": sum(1 for r in ok if r.get("declined")),
        "tokens": tokens,
        "cost_usd": round(
            sum(estimate_cost(r.get("model"), r.get("tokens")) for r in ok), 4
        ),
        "by_model": by_model,
        "recent": records[-15:][::-1],
    }


def load_rules(path: str | None = None) -> list[dict]:
    p = Path(path or ALERT_RULES)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def check_alerts(summary: dict, rules: list[dict]) -> list[dict]:
    """Which alert rules does the summary break?

    Each rule looks like {"name": "Too many errors", "metric": "error_rate", "above": 0.05,
    "min_requests": 10, "action": "Check the model provider's status page"}.

    Rules (tests/test_alerts.py checks each one):
    - skip a rule when summary["requests"] is less than rule.get("min_requests", 1)
    - skip a rule when summary[rule["metric"]] is missing or None
    - the rule fires when that value is greater than rule["above"]
    - return one dict per firing rule, in the order of the rules:
        {"name": ..., "metric": ..., "value": the value, "above": ..., "action": rule.get("action", "")}
    """
    fired = []
    for rule in rules:
        if summary.get("requests", 0) < rule.get("min_requests", 1):
            continue  # too few requests to judge
        value = summary.get(rule["metric"])
        if value is None or value <= rule["above"]:
            continue  # missing, or within limits
        fired.append(
            {
                "name": rule["name"],
                "metric": rule["metric"],
                "value": value,
                "above": rule["above"],
                "action": rule.get("action", ""),
            }
        )
    return fired
