"""Run every case of the evaluation suite through the chatbot and apply the code checks.

Run: .venv/Scripts/python.exe -m scripts.run_eval
Options: --ids FUN-01 SAF-02 (only these cases), --dimension safety (only one dimension), --label "Baseline"
A partial run saves to data/eval_results_partial.* and leaves the full results alone; add --merge to also put its
dimension numbers into the summary (used to show the gate failing when something is broken).
Uses the real answer model, so calls are paced to stay under the rate limit. Saves
data/eval_results.csv and .json (one row per case) and data/eval_summary.json (one entry per dimension).
"""
import argparse

from app.answer import answer
from app.config import RETRIEVAL_MODE, ROOT
from app.eval_suite import DIMENSIONS, SUITE_PATH, load_suite, run_suite, save_results, summarize, update_summary
from app.llm import reset_usage, usage_snapshot

PAUSE_PER_CALL = 3.0  # seconds after each model call


def refusal_sentence() -> str | None:
    """The fixed refusal sentence, once the safety phase has defined one."""
    try:
        from app.config import REFUSAL_SENTENCE
        return REFUSAL_SENTENCE
    except ImportError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="+", help="run only these case ids")
    parser.add_argument("--dimension", choices=DIMENSIONS, help="run only one dimension")
    parser.add_argument("--label", default="", help="a name for this run, saved in the summary")
    parser.add_argument("--merge", action="store_true", help="a partial run (--ids/--dimension) also merges its dimension numbers into the summary")
    args = parser.parse_args()

    try:
        cases = load_suite()
    except ValueError as err:
        print(f"ERROR: {err}")
        return 1
    if args.ids:
        cases = [c for c in cases if c["id"] in args.ids]
    if args.dimension:
        cases = [c for c in cases if c["dimension"] == args.dimension]
    if not cases:
        print("ERROR: no cases selected.")
        return 1

    print(f"Running {len(cases)} cases from {SUITE_PATH.name} in {RETRIEVAL_MODE} mode...", flush=True)

    def show(row):
        mark = "OK  " if row["passed"] else "FAIL"
        extra = "" if row["passed"] else "  <- " + ("; ".join(row["failed"]) or row["error"])[:90]
        print(f"{mark} {row['id']:<7} want {row['expected_behaviour']:<7} got {row['actual']:<7}{extra}", flush=True)

    rows = run_suite(cases, lambda q, prev: answer(q, previous_question=prev), RETRIEVAL_MODE, reset_usage, usage_snapshot,
                     pause_per_call=PAUSE_PER_CALL, refusal_sentence=refusal_sentence(), progress=show)

    partial = bool(args.ids or args.dimension)  # a partial run must never overwrite the full results
    if partial:
        save_results(rows, ROOT / "data" / "eval_results_partial.csv", ROOT / "data" / "eval_results_partial.json")
    else:
        save_results(rows)
    summary = summarize(rows)
    if not partial:
        update_summary({**{d: v for d, v in summary.items() if v["cases"]}, "run": {"label": args.label, "mode": RETRIEVAL_MODE, "cases": len(rows)}})
    elif args.merge:
        update_summary({d: v for d, v in summary.items() if v["cases"]})  # numbers only: the full run's label, mode and case count stay

    print(f"\n{'dimension':<12}{'cases':>6}{'passed':>8}{'pass rate':>11}")
    for dimension, s in summary.items():
        if s["cases"]:
            print(f"{dimension:<12}{s['cases']:>6}{s['passed']:>8}{s['pass_rate']:>11.0%}")
    total = sum(s["passed"] for s in summary.values())
    print(f"{'all':<12}{len(rows):>6}{total:>8}{total / len(rows):>11.0%}")
    if partial:
        print("\nSaved to data/eval_results_partial.* (a partial run: the full results are untouched)")
    else:
        print("\nSaved to data/eval_results.csv, data/eval_results.json and data/eval_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
