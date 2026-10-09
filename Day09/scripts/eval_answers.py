"""Day 8: evaluate chatbot answers with code checks and, optionally, a judge model.

    python -m scripts.eval_answers --no-judge     (Activity 1: code checks only, no model calls)
    python -m scripts.eval_answers                (Activity 2: code checks + the judge)
    python -m scripts.eval_answers --live         (ask the chatbot the Day 6 test questions first)
    python -m scripts.eval_answers --live --questions data/my_test_questions.csv --name my_docs   (homework)

The answers file has the columns id, question, expected_answer, expected_behaviour, bot_answer,
declined, sources, context, and optionally human_correct and human_grounded (yes or no).
Results are saved to data/answer_eval_results.csv. --live also saves the answers it collected
to data/answers_live.csv, in the same format, ready for you to label.
"""

import argparse
import csv
import time

from app.answer_checks import check_behaviour, check_citations
from app.judge import judge_answer

ANSWERS = "data/Day08_Slide25_chatbot_answers.csv"
QUESTIONS = "data/Day06_Slide25_test_questions.csv"
FIELDS = [
    "id",
    "question",
    "expected_answer",
    "expected_behaviour",
    "bot_answer",
    "declined",
    "sources",
    "context",
    "human_correct",
    "human_grounded",
    "seconds",
]


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields=None):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields or list(rows[0]), extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def generate_answers(questions, mode=None, name="it_policies"):
    """Ask the chatbot every question, the same way the app does, and record what it used."""
    from app.advanced import RAG_MODE, retrieve
    from app.rag import MIN_SCORE, answer, format_sources

    rows = []
    for i, q in enumerate(questions, 1):
        start = time.perf_counter()
        r = retrieve(q["question"], mode=mode or RAG_MODE, name=name)
        result = answer(r["query"], retrieve=lambda _: r["chunks"])
        kept = [
            c for c in r["chunks"] if c["score"] >= MIN_SCORE
        ]  # the chunks the prompt used
        rows.append(
            {
                "id": i,
                "question": q["question"],
                "expected_answer": q["expected_answer"],
                "expected_behaviour": q["expected_behaviour"],
                "bot_answer": result["answer"],
                "declined": "yes" if result["declined"] else "no",
                "sources": "; ".join(result["sources"]),
                "context": format_sources(kept) if result["sources"] else "",
                "human_correct": "",
                "human_grounded": "",
                "seconds": round(time.perf_counter() - start, 2),
            }
        )
        print(f"  asked {i}/{len(questions)}", end="\r", flush=True)
    print()
    return rows


def evaluate(rows, use_judge=True, client=None):
    """Run every check on every answer. Returns (results, summary)."""
    results = []
    for row in rows:
        declined = row["declined"] == "yes"
        n_sources = len([s for s in row["sources"].split(";") if s.strip()])
        cite = check_citations(row["bot_answer"], n_sources, declined)
        behave = check_behaviour(declined, row["expected_behaviour"])
        verdict = (
            judge_answer(
                row["question"],
                row["expected_answer"],
                row["bot_answer"],
                row["context"],
                client=client,
            )
            if use_judge
            else {"correct": None, "grounded": None, "reason": ""}
        )
        results.append(
            {
                **row,
                "citation_problems": "; ".join(cite),
                "behaviour_problems": "; ".join(behave),
                "judge_correct": verdict["correct"],
                "judge_grounded": verdict["grounded"],
                "judge_reason": verdict["reason"],
            }
        )
    n = len(results)
    summary = {
        "answers": n,
        "citation_pass_rate": round(
            sum(not r["citation_problems"] for r in results) / n, 2
        ),
        "behaviour_rate": round(
            sum(not r["behaviour_problems"] for r in results) / n, 2
        ),
    }
    if use_judge:
        summary["judge_correct_rate"] = round(
            sum(r["judge_correct"] is True for r in results) / n, 2
        )
        summary["judge_grounded_rate"] = round(
            sum(r["judge_grounded"] is True for r in results) / n, 2
        )
        summary["judge_unreadable"] = sum(r["judge_correct"] is None for r in results)
        labelled = [r for r in results if r.get("human_correct") in ("yes", "no")]
        for kind in ("correct", "grounded"):
            agree = [
                r
                for r in labelled
                if r[f"judge_{kind}"] is (r[f"human_{kind}"] == "yes")
            ]
            if labelled:
                summary[f"agreement_{kind}"] = f"{len(agree)}/{len(labelled)}"
    timed = [float(r["seconds"]) for r in results if r.get("seconds")]
    if timed:
        summary["avg_seconds"] = round(sum(timed) / len(timed), 2)
    return results, summary


def yn(v):
    return {True: "yes", False: "NO", None: " ? "}[v]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", default=ANSWERS)
    ap.add_argument(
        "--no-judge", action="store_true", help="code checks only: no model calls"
    )
    ap.add_argument(
        "--live", action="store_true", help="ask the chatbot the questions first"
    )
    ap.add_argument("--questions", default=QUESTIONS)
    ap.add_argument(
        "--name", default="it_policies", help="collection name (with --live)"
    )
    ap.add_argument(
        "--mode", default=None, help="retrieval mode (with --live); default RAG_MODE"
    )
    args = ap.parse_args()

    if args.live:
        rows = generate_answers(read_csv(args.questions), args.mode, args.name)
        write_csv("data/answers_live.csv", rows, FIELDS)
        print("Saved the answers to data/answers_live.csv\n")
    else:
        rows = read_csv(args.answers)
    results, summary = evaluate(rows, use_judge=not args.no_judge)

    for r in results:
        problems = [p for p in (r["citation_problems"], r["behaviour_problems"]) if p]
        line = f"{str(r['id']):>3}  {'OK  ' if not problems else 'FAIL'}  {r['question'][:52]:52}"
        if not args.no_judge:
            line += f"  judge: correct {yn(r['judge_correct'])}  grounded {yn(r['judge_grounded'])}"
        print(line)
        for p in problems:
            print(f"           code check: {p}")
        if not args.no_judge and (
            r["judge_correct"] is not True or r["judge_grounded"] is not True
        ):
            print(f"           judge: {r['judge_reason']}")
    write_csv("data/answer_eval_results.csv", results)
    print("\nSummary: " + "   ".join(f"{k} {v}" for k, v in summary.items()))
    print("Full results: data/answer_eval_results.csv")


if __name__ == "__main__":
    main()
