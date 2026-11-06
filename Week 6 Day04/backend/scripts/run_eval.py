"""Run the prototype over the evaluation set and print the score. Run from backend/:

    python -m scripts.run_eval                               # Day 3 prompt, the 50 real cases
    python -m scripts.run_eval --prompt extract_v2 --set all # a new prompt, real and synthetic cases

Each run is saved to engagement/eval/runs/<prompt>__<set>.json; the Evaluation → Before and after tab compares them.
"""

import argparse

from app.evaluation.service import run_set
from app.llm import llm_client


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default="extract", help="a file in backend/app/prototype/prompts/, without .md")
    ap.add_argument("--set", default="real", choices=["real", "synthetic", "all"])
    a = ap.parse_args()
    r = run_set(a.set, a.prompt, llm_client())
    s = r["score"]
    print(f"Run {r['name']}: {r['cases']} cases, {s['overall']['correct']} of {s['overall']['total']} fields right ({s['overall']['accuracy']}%)")
    print("\nBy field")
    for f, v in s["per_field"].items():
        print(f"  {f:16} {v['accuracy']:5}%  ({v['correct']}/{v['total']})")
    print("\nBy slice")
    for k, v in s["per_slice"].items():
        print(f"  {k:18} {v['accuracy']:5}%  ({v['correct']}/{v['total']})")
    print(f"\nRules agree with Tom on {r['rules']['agree']} of {r['rules']['compared']} decisions")
    if s["errors"]:
        print(f"\n{len(s['errors'])} wrong fields")
        for e in s["errors"]:
            print(f"  {e['case_id']}  {e['field']:15} got {e['got']!r}, expected {e['expected']!r}")


if __name__ == "__main__":
    main()
