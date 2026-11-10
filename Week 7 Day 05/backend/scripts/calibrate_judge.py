"""Run an LLM judge over the 50 real cases and calibrate it against Tom's failure tags. Run from backend/:

    python -m scripts.calibrate_judge wrong_date        # evals/judges/wrong_date.md
    python -m scripts.calibrate_judge wrong_date_v1     # your improved prompt

A judge you can trust catches Tom's failures (caught) without flagging good values (cleared), and agrees with him
beyond chance (kappa). The disagreements tell you what to change in the prompt.
"""

import argparse

from app.evaluation.service import run_judge
from app.llm import llm_client


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", help="a file in evals/judges/, without .md")
    r = run_judge(ap.parse_args().prompt, llm_client())
    a = r["agreement"]
    print(f"Judge {r['prompt']} on {a['n']} cases, looking for {r['failure_type']} in {r['field']}")
    print(f"  caught  {a['caught']}   (Tom's failures the judge flags: {a['tp']} of {a['tp'] + a['fn']})")
    print(f"  cleared {a['cleared']}   (good values the judge passes: {a['tn']} of {a['tn'] + a['fp']})")
    print(f"  kappa   {a['kappa']}   (agreement {a['percent']}%)")
    if a["disagreements"]:
        print("\nDisagreements")
        for cid in a["disagreements"]:
            v = r["verdicts"][cid]
            print(f"  {cid}  judge {v['verdict']}, Tom {v['expert']}  value {v['value']!r}  · {v['reason']}")


if __name__ == "__main__":
    main()
