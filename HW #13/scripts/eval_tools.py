"""Day 11 homework, Task 3: check that the assistant picks the right tools for each request.

    python -m scripts.eval_tools --tests data/my_tool_tests.csv

The file has the columns request and expected_tools: the tool names separated by |, or none.
Changes are never approved during the check, so no ticket is changed.
"""

import argparse
import csv

from app.tool_loop import run_tool_loop

TESTS = "data/Day11_HW_Slide05_tool_tests_template.csv"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tests", default=TESTS)
    args = ap.parse_args()
    with open(args.tests, newline="", encoding="utf-8") as f:
        tests = list(csv.DictReader(f))
    right = 0
    for t in tests:
        expected = (
            set()
            if t["expected_tools"].strip() in ("", "none")
            else set(t["expected_tools"].split("|"))
        )
        out = run_tool_loop(t["request"], confirm=lambda summary: False)
        used = {c["name"] for c in out["calls"]}
        ok = used == expected
        right += ok
        print(
            f"{'ok   ' if ok else 'WRONG'} {t['request'][:60]:60}  expected {sorted(expected) or ['none']}"
            f"  used {sorted(used) or ['none']}"
        )
    print(f"\nRight tools chosen: {right}/{len(tests)}")


if __name__ == "__main__":
    main()
