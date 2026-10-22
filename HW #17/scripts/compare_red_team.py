"""Day 17: two red-team reports side by side: which attacks still work?

python -m scripts.compare_red_team before after      (reads logs/red_team_before.json and _after.json)
"""

import json
import sys
from pathlib import Path


def load(label: str) -> dict:
    return json.loads(Path(f"logs/red_team_{label}.json").read_text(encoding="utf-8"))


def main(a: str, b: str):
    ra, rb = load(a), load(b)
    after = {r["id"]: r for r in rb["results"]}
    print(f"{'id':4} {'risk':40} {a:>10} {b:>10}   what stopped it")
    for r in ra["results"]:
        s = after.get(r["id"])
        if s is None:
            continue
        mark = lambda x: "WORKED" if x["succeeded"] else "stopped"
        why = (
            ""
            if s["succeeded"]
            else ("; ".join(s["guardrail"])[:50] or "the model, or the missing tool")
        )
        print(f"{r['id']:4} {r['owasp'][:40]:40} {mark(r):>10} {mark(s):>10}   {why}")
    for label, rep in ((a, ra), (b, rb)):
        x = rep["summary"]
        print(
            f"{label:>10}: {x['succeeded']} of {x['attacks']} worked   settings {rep['settings']}"
        )


if __name__ == "__main__":
    labels = sys.argv[1:] or ["before", "after"]
    main(labels[0], labels[1])
