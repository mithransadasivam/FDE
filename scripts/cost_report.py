"""Day 3 homework, Task 3: turn data/usage.csv into a per-model cost report.

Run: python -m scripts.cost_report [path] [calls_per_day]
Prices come from the registry in .env, so the output-token share is computed from the
same numbers that priced each call.
"""

import csv
import sys

from dotenv import load_dotenv

from app.chatbot import prices_for

USAGE = "data/usage.csv"
DAYS_PER_MONTH = 30


def load_usage(path=USAGE):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def summarise(rows, prices, calls_per_day=1000):
    """One entry per model. prices: model -> (in $/1M, out $/1M)."""
    out = {}
    for r in rows:
        m = out.setdefault(
            r["model"], {"calls": 0, "in_tok": 0, "out_tok": 0, "cost": 0.0}
        )
        m["calls"] += 1
        m["in_tok"] += int(r["prompt_tokens"])
        m["out_tok"] += int(r["completion_tokens"])
        m["cost"] += float(r["cost"])
    for model, m in out.items():
        _in_p, out_p = prices.get(model, (0.0, 0.0))
        m["out_cost"] = m["out_tok"] / 1e6 * out_p
        m["per_call"] = m["cost"] / m["calls"]
        m["monthly"] = m["per_call"] * calls_per_day * DAYS_PER_MONTH
    return out


def output_share(summary):
    """Share of total cost from output tokens, or None if nothing was charged."""
    total = sum(m["cost"] for m in summary.values())
    return sum(m["out_cost"] for m in summary.values()) / total if total else None


def format_report(summary, calls_per_day=1000):
    lines = [
        f"{'model':32} {'calls':>5} {'in_tok':>8} {'out_tok':>8} {'cost':>9} {'$/call':>9}"
    ]
    for model, m in summary.items():
        lines.append(
            f"{model:32} {m['calls']:5} {m['in_tok']:8,} {m['out_tok']:8,} "
            f"${m['cost']:8.4f} ${m['per_call']:8.5f}"
        )
    share = output_share(summary)
    lines.append("")
    lines.append(
        "output tokens are "
        + (f"{share:.0%} of total cost" if share is not None else "n/a (no cost)")
    )
    lines.append(f"projection at {calls_per_day:,} calls/day ({DAYS_PER_MONTH} days):")
    for model, m in summary.items():
        lines.append(f"  {model:32} ${m['monthly']:,.2f}/month")
    return "\n".join(lines)


def main():
    load_dotenv()
    path = sys.argv[1] if len(sys.argv) > 1 else USAGE
    per_day = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    rows = load_usage(path)
    prices = {r["model"]: prices_for(r["model"]) for r in rows}
    print(format_report(summarise(rows, prices, per_day), per_day))


if __name__ == "__main__":
    main()
