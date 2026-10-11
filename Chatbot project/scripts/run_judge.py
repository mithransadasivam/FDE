"""Score the answered cases of the last evaluation run with the judge model.

Run: .venv/Scripts/python.exe -m scripts.run_judge
Reads data/eval_results.json (written by scripts.run_eval), asks the judge (JUDGE_MODEL) five yes/no questions
per answered case, saves data/eval_judged.csv and adds the averages to data/eval_summary.json.
"""
import csv
import json

from app.eval_suite import RESULTS_JSON, ROOT, update_summary
from app.judge import judge_rows, summarize_scores
from app.llm import LLMError

JUDGED_CSV = ROOT / "data" / "eval_judged.csv"
PAUSE = 2.0  # seconds between judge calls, to stay under the rate limit


def main() -> int:
    try:
        rows = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("ERROR: no evaluation results found. Run scripts.run_eval first.")
        return 1

    def show(entry):
        if entry["judge_error"]:
            print(f"ERR  {entry['id']:<7} {entry['judge_error']}", flush=True)
        else:
            flags = "".join(("Y" if entry[k] else "n") if entry[k] is not None else "-" for k in
                            ("correct", "faithfulness", "answer_relevance", "context_recall"))
            print(f"{entry['id']:<8} correct/faithful/relevant/recall = {flags}  precision {entry['context_precision']:.2f}  {entry['reason'][:70]}", flush=True)

    try:
        scored = judge_rows(rows, pause=PAUSE, progress=show)
    except LLMError as err:
        print(f"ERROR: {err}")
        return 1

    columns = ["id", "dimension", "correct", "faithfulness", "answer_relevance", "context_precision", "context_recall",
               "recall_in_code", "reason", "judge_error"]
    with open(JUDGED_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows({c: s.get(c) for c in columns} for s in scored)

    summary = summarize_scores(scored)
    update_summary({"quality": summary["quality"], "ragas": summary["ragas"], "judge": {"model_variable": "JUDGE_MODEL", "errors": summary["judge_errors"]}})
    print(f"\nJudged {len(scored)} answered cases ({summary['judge_errors']} judge errors).")
    print("quality:", summary["quality"])
    print("ragas:  ", summary["ragas"])
    print(f"Saved to {JUDGED_CSV.name} and data/eval_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
