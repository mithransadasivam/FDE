"""Day 16: did the optimisations cost quality? Ask the Day 6 test questions through the service
exactly as users do (routing as configured, cache off, so every answer is fresh), check every
answer with the Day 8 checks and judge, and apply the Day 8 thresholds.

python -m scripts.quality_recheck                 (uses ROUTING from .env)
ROUTING=1 python -m scripts.quality_recheck       (with routing)

Exit code 0 means PASS, 1 means FAIL, like the Day 8 quality gate.
"""

import argparse
import csv
import os
import sys
import time

from app import service
from app.quality_gate import load_thresholds, quality_gate
from app.rag import format_sources
from scripts.eval_answers import evaluate

QUESTIONS = "data/Day06_Slide25_test_questions.csv"
THRESHOLDS = "data/Day08_Slide37_quality_thresholds.json"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--questions", default=QUESTIONS)
    p.add_argument("--thresholds", default=THRESHOLDS)
    p.add_argument("--no-judge", action="store_true")
    a = p.parse_args()
    os.environ["CACHE"] = (
        "0"  # every answer fresh: a cached answer proves nothing about quality
    )
    with open(a.questions, newline="", encoding="utf-8") as f:
        questions = list(csv.DictReader(f))
    print(
        f"Routing {'on' if service.routing_on() else 'off'}; asking {len(questions)} questions ..."
    )
    rows, cost = [], 0.0
    for i, q in enumerate(questions, 1):
        start = time.perf_counter()
        found = service.find(q["question"])
        r = service.answer(q["question"])
        cost += r["cost_usd"]
        rows.append(
            {
                "id": i,
                "question": q["question"],
                "expected_answer": q["expected_answer"],
                "expected_behaviour": q["expected_behaviour"],
                "bot_answer": r["answer"],
                "declined": "yes" if r["declined"] else "no",
                "sources": "; ".join(r["sources"]),
                "context": format_sources(found["kept"]) if r["sources"] else "",
                "human_correct": "",
                "human_grounded": "",
                "seconds": round(time.perf_counter() - start, 2),
                "route": r["route"] or "declined",
            }
        )
        print(
            f"  {i:2}. {r['route'] or 'declined':8} {r['model'] or '':30} {q['question'][:50]}"
        )
    results, summary = evaluate(rows, use_judge=not a.no_judge)
    thresholds = {
        k: v for k, v in load_thresholds(a.thresholds).items() if k[4:] in summary
    }
    problems = quality_gate(summary, thresholds)
    print()
    for key, value in thresholds.items():
        metric = key[4:]
        failed = any(pr.startswith(metric + " ") for pr in problems)
        print(
            f"  {'FAIL' if failed else 'ok  '}  {metric:22} {summary.get(metric)!s:>8}   "
            f"needs {'>=' if key.startswith('min_') else '<='} {value}"
        )
    for r in results:
        if (
            r["citation_problems"]
            or r["behaviour_problems"]
            or r["judge_correct"] is False
        ):
            print(
                f"  check: [{r['route']}] {r['question']}  {r['citation_problems']}"
                f"{r['behaviour_problems']} {r['judge_reason']}"
            )
    print(f"\nCost of these {len(rows)} answers: ${cost:.4f}")
    print("QUALITY GATE:", "PASS" if not problems else "FAIL")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
