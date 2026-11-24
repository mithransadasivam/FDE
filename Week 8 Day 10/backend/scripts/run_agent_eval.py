"""Run the operations agent on the 20 evaluation cases, in shadow mode (Day 9 homework).

From backend/, with the bank's systems running (npm run dev):
    python -m scripts.run_agent_eval --prompt ops_v1
    python -m scripts.run_agent_eval --prompt ops_v2 --case E06      (one case, not saved)
"""

import argparse

from app.agent.evaluate import evaluate

ap = argparse.ArgumentParser()
ap.add_argument("--prompt", default="ops_v1")
ap.add_argument("--case", action="append", help="E01..E20 or a ticket id; repeat for more")
a = ap.parse_args()
out = evaluate(a.prompt, a.case)
print(f"\n{a.prompt}: {out['passed']} of {out['total']} passed" if out["scored"] else f"\n{a.prompt}: runs saved, not scored (score_run() is not built)")
print(f"Tokens: {out['tokens_in']:,} in, {out['tokens_out']:,} out · ${out['cost_usd']:.4f} on the class model")
