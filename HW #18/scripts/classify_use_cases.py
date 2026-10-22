"""Day 18: classify every use case in the inventory and write the inventory page.

python -m scripts.classify_use_cases                                   (the class inventory)
python -m scripts.classify_use_cases --use-cases data/my_use_cases.json   (homework: add your capstone)

Prints one line per use case and writes governance/use_case_inventory.md, the page a governance
board would read first. The categories are a first sorting, not legal advice.
"""

import argparse
import json
from pathlib import Path

from app.ai_act import classify_use_case

USE_CASES = "data/Day18_Slide09_use_cases.json"
OUT = "governance/use_case_inventory.md"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--use-cases", default=USE_CASES)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()
    cases = json.loads(Path(args.use_cases).read_text(encoding="utf-8"))
    lines = [
        "# AI use-case inventory",
        "",
        "A first sorting by EU AI Act risk category (scripts/classify_use_cases.py). Not legal advice:",
        "borderline cases go to the compliance team with this page as the starting point.",
        "",
        "| Id | Use case | Owner | Category | Why | Applies from | Obligations |",
        "|---|---|---|---|---|---|---|",
    ]
    print(f"{'id':6} {'use case':26} {'category':11} why")
    for uc in cases:
        r = classify_use_case(uc)
        print(f"{uc['id']:6} {uc['name'][:26]:26} {r['category']:11} {r['reason']}")
        lines.append(
            f"| {uc['id']} | {uc['name']}: {uc['purpose']} | {uc['owner']} | **{r['category']}** | "
            f"{r['reason']} | {r['applies_from']} | {'; '.join(r['obligations'])} |"
        )
    lines += [
        "",
        "Every AI system, whatever its category: staff who use it need AI literacy (Article 4).",
    ]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
