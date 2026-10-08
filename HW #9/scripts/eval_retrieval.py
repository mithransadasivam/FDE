"""Day 7: measure one retrieval mode on the test set. No answers are written, so it is quick.

    python -m scripts.eval_retrieval --mode vector          (Activity 1: the baseline)
    python -m scripts.eval_retrieval --mode hybrid          (Activity 2)
    python -m scripts.eval_retrieval --mode rerank          (Activity 3)
    python -m scripts.eval_retrieval --questions data/my_retrieval_test_set.csv --name my_docs   (homework)
Results are printed and saved to data/retrieval_results_<mode>.csv.
"""

import argparse
import csv
import time

from app.advanced import MODES, retrieve
from app.retrieval_eval import load_test_set, score_question, summarise

TEST_SET = "data/Day07_Slide09_retrieval_test_set.csv"


def evaluate(mode, questions, name="it_policies", k=4, quiet=False):
    rows = []
    for q in questions:
        start = time.perf_counter()
        r = retrieve(
            q["question"],
            mode=mode,
            previous=q.get("previous_question") or None,
            k=k,
            name=name,
        )
        ms = (time.perf_counter() - start) * 1000
        s = score_question(r["chunks"], q["expected_source"], q["evidence"], k)
        rows.append(
            {
                **q,
                "mode": mode,
                "searched_for": r["query"],
                "rank": s["rank"] or "",
                "hit": s["hit"],
                "rr": round(s["rr"], 3),
                "ms": round(ms),
                "model_calls": r["model_calls"],
                "top_source": f"{r['chunks'][0]['source']}, page {r['chunks'][0]['page']}"
                if r["chunks"]
                else "",
            }
        )
        if not quiet:
            rank = f"rank {s['rank']}" if s["rank"] else "not found"
            print(
                f"{'HIT ' if s['hit'] else 'MISS'} {rank:9} {q['kind']:10} {q['question'][:60]}"
            )
            if r["query"] != q["question"]:
                print(f"               searched for: {r['query'][:80]}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="vector", choices=MODES)
    ap.add_argument("--questions", default=TEST_SET)
    ap.add_argument("--name", default="it_policies", help="collection name")
    ap.add_argument("--k", type=int, default=4, help="chunks the chatbot would use")
    args = ap.parse_args()
    rows = evaluate(args.mode, load_test_set(args.questions), args.name, args.k)
    out = f"data/retrieval_results_{args.mode}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    s = summarise(rows)
    print(
        f"\nMode: {args.mode}   Hit rate @{args.k}: {s['hit_rate']:.0%}   MRR: {s['mrr']:.2f}"
    )
    print("By kind: " + "   ".join(f"{k} {v}" for k, v in s["by_kind"].items()))
    print(
        f"Average time per question: {sum(r['ms'] for r in rows) / len(rows):.0f} ms   "
        f"Model calls per question: {rows[0]['model_calls']}"
    )
    print(f"Full results: {out}")


if __name__ == "__main__":
    main()
