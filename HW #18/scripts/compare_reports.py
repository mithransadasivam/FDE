"""Day 16: put two or more load test reports side by side.

python -m scripts.compare_reports baseline after       (reads logs/load_baseline.json, logs/load_after.json)
"""

import json
import sys
from pathlib import Path

ROWS = [
    "requests",
    "errors",
    "p50_seconds",
    "p95_seconds",
    "throughput_per_second",
    "cost_per_1000",
    "tokens_per_question",
    "cache_hit_rate",
    "routes",
]


def main(labels):
    reports = [
        json.loads(Path(f"logs/load_{x}.json").read_text(encoding="utf-8"))["report"]
        for x in labels
    ]
    print(f"{'':24}" + "".join(f"{r['label']:>22}" for r in reports))
    for row in ROWS[:-1]:
        print(f"{row:24}" + "".join(f"{r.get(row)!s:>22}" for r in reports))
    print("routes")
    for r in reports:
        print(f"  {r['label']:22}" + "  ".join(f"{k} {v}" for k, v in r["routes"].items()))


if __name__ == "__main__":
    main(sys.argv[1:] or ["baseline", "after"])
