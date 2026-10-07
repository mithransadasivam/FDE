"""Day 7, Activity 4: run the test set through every retrieval mode and compare them.

    python -m scripts.compare_modes
    python -m scripts.compare_modes --questions data/my_retrieval_test_set.csv --name my_docs   (homework)
The table is printed and saved to data/retrieval_comparison.csv.
"""

import argparse
import csv

from app.advanced import MODES
from app.retrieval_eval import load_test_set, summarise
from scripts.eval_retrieval import TEST_SET, evaluate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=TEST_SET)
    ap.add_argument("--name", default="it_policies", help="collection name")
    ap.add_argument("--modes", nargs="+", default=MODES, choices=MODES)
    args = ap.parse_args()
    questions = load_test_set(args.questions)
    table, kinds = [], []
    for mode in args.modes:
        print(f"Running {mode} ...")
        rows = evaluate(mode, questions, args.name, quiet=True)
        s = summarise(rows)
        kinds = list(s["by_kind"])
        table.append(
            {
                "mode": mode,
                "hit_rate": f"{s['hit_rate']:.0%}",
                "mrr": f"{s['mrr']:.2f}",
                **s["by_kind"],
                "avg_ms": round(sum(r["ms"] for r in rows) / len(rows)),
                "model_calls_per_question": rows[0]["model_calls"],
            }
        )
    print()
    head = (
        f"{'mode':8} {'hit@4':>6} {'MRR':>5}  "
        + "".join(f"{k[:10]:>11}" for k in kinds)
        + f"{'ms':>7} {'calls':>6}"
    )
    print(head)
    for t in table:
        print(
            f"{t['mode']:8} {t['hit_rate']:>6} {t['mrr']:>5}  "
            + "".join(f"{t[k]:>11}" for k in kinds)
            + f"{t['avg_ms']:>7} {t['model_calls_per_question']:>6}"
        )
    with open("data/retrieval_comparison.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    print("\nSaved: data/retrieval_comparison.csv")


if __name__ == "__main__":
    main()
