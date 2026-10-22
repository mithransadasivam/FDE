"""Day 18: check any risk register file, and list the reviews that are overdue.

python -m scripts.check_register                                          (governance/risk_register.json)
python -m scripts.check_register --register governance/capstone_risk_register.json   (homework)

Exit code 0 when the register passes, 1 when it has problems.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from app.risk_register import FUNCTIONS, check_register, overdue, rating


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--register", default="governance/risk_register.json")
    args = ap.parse_args()
    risks = json.loads(Path(args.register).read_text(encoding="utf-8"))
    problems = check_register(risks)
    for r in risks:
        try:
            rt = rating(r["likelihood"], r["impact"])
            score = f"{rt['score']:>2} {rt['level']}"
        except (KeyError, TypeError):
            score = " ? "
        print(
            f"  {r.get('id', '?'):5} {str(r.get('function')):8} {score:10} {str(r.get('status')):10} {r.get('title', '')[:60]}"
        )
    per = Counter(r.get("function") for r in risks)
    print("\n  by function: " + ", ".join(f"{f} {per.get(f, 0)}" for f in FUNCTIONS))
    try:
        late = overdue(risks)
        print(f"  overdue reviews: {', '.join(late) or 'none'}")
    except NotImplementedError:
        print("  overdue reviews: (homework, Task 1: overdue() is not written yet)")
    for p in problems:
        print(f"  PROBLEM  {p}")
    print(
        f"\nRegister {args.register}: {'PASS' if not problems else 'FAIL'} ({len(risks)} risks)"
    )
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
