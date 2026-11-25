"""Homework: the crash test. 20 case workflows as Helen, one crash armed in each, then each case scored from the bank's records.

From backend/, with npm run dev running (the worker must be up):
    python -m scripts.run_crashes
"""

from app.workflow.crashtest import run

out = run()
if out["scored"]:
    print(f"\n{out['passed']} of {out['total']} cases passed · {out['crashes_fired']} crashes fired · {out['seconds']} s")
else:
    print(f"\nCases run, not scored: score_case() is not built (homework Task 1) · {out['crashes_fired']} crashes fired")
