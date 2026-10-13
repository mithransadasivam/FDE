"""Day 8, Activity 3: run the evaluations and decide PASS or FAIL against agreed thresholds.

    python -m scripts.quality_gate                    (uses RAG_MODE from .env)
    python -m scripts.quality_gate --mode vector      (try a weaker pipeline: the gate should fail)
    python -m scripts.quality_gate --name my_docs --retrieval-questions data/my_retrieval_test_set.csv \
        --answer-questions data/my_test_questions.csv --thresholds data/my_quality_thresholds.json   (homework)

It runs the Day 7 retrieval test set and asks the chatbot the Day 6 test questions, checks every
answer (code checks and the judge), then compares the numbers with the thresholds file.
Exit code 0 means PASS, 1 means FAIL, so other tools can stop a release when quality drops.
"""

import argparse
import json
import sys

from app.advanced import RAG_MODE
from app.quality_gate import load_thresholds, quality_gate
from app.retrieval_eval import load_test_set, summarise
from scripts.eval_answers import QUESTIONS, evaluate, generate_answers, read_csv
from scripts.eval_retrieval import TEST_SET
from scripts.eval_retrieval import evaluate as evaluate_retrieval

THRESHOLDS = "data/Day08_Slide37_quality_thresholds.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default=RAG_MODE)
    ap.add_argument("--name", default="it_policies", help="collection name")
    ap.add_argument("--retrieval-questions", default=TEST_SET)
    ap.add_argument("--answer-questions", default=QUESTIONS)
    ap.add_argument("--thresholds", default=THRESHOLDS)
    args = ap.parse_args()

    print(f"Mode: {args.mode}\n1/2 Retrieval test set ...")
    retrieval = summarise(
        evaluate_retrieval(
            args.mode, load_test_set(args.retrieval_questions), args.name, quiet=True
        )
    )
    print("2/2 Asking the chatbot and checking the answers ...")
    _, answers = evaluate(
        generate_answers(read_csv(args.answer_questions), args.mode, args.name)
    )
    summary = {
        "hit_rate": round(retrieval["hit_rate"], 2),
        "mrr": round(retrieval["mrr"], 2),
        **{k: v for k, v in answers.items() if isinstance(v, (int, float))},
    }

    thresholds = load_thresholds(args.thresholds)
    problems = quality_gate(summary, thresholds)
    print()
    for key, value in thresholds.items():
        metric = key[4:]
        failed = any(p.startswith(metric + " ") for p in problems)
        print(
            f"  {'FAIL' if failed else 'ok  '}  {metric:22} {str(summary.get(metric, 'missing')):>8}   "
            f"needs {'>=' if key.startswith('min_') else '<='} {value}"
        )
    with open("data/quality_report.json", "w", encoding="utf-8") as f:
        json.dump(
            {"mode": args.mode, "summary": summary, "problems": problems}, f, indent=2
        )
    print(
        f"\nQUALITY GATE: {'FAIL' if problems else 'PASS'}   (report: data/quality_report.json)"
    )
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
