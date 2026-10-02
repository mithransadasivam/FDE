"""Day 6, Activity 4: run every test question and save the results.

    python -m scripts.run_tests
    python -m scripts.run_tests --questions data/my_test_questions.csv --name my_docs   (homework)
The questions file has columns question, expected_answer, expected_behaviour (answer or decline).
Results are printed and saved to data/rag_test_results.csv.
"""

import argparse
import csv
from functools import partial

from app.indexing import search
from app.rag import answer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default="data/Day06_Slide25_test_questions.csv")
    ap.add_argument("--name", default="it_policies", help="collection name")
    args = ap.parse_args()
    with open(args.questions, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    results, ok = [], 0
    for row in rows:
        r = answer(row["question"], retrieve=partial(search, name=args.name))
        got = "decline" if r["declined"] else "answer"
        match = got == row["expected_behaviour"]
        ok += match
        results.append(
            {
                **row,
                "got": got,
                "behaviour_ok": match,
                "bot_answer": r["answer"],
                "sources": "; ".join(r["sources"]),
            }
        )
        print(f"{'OK  ' if match else 'MISS'} {got:7} {row['question'][:60]}")
        print(f"       bot:      {' '.join(r['answer'].split())[:100]}")
        print(f"       expected: {row['expected_answer']}\n")

    with open("data/rag_test_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)
    print(
        f"Behaviour correct for {ok} of {len(rows)} questions. Full results: data/rag_test_results.csv"
    )
    print(
        "Now check each answer against the expected answer, and each citation against the document."
    )


if __name__ == "__main__":
    main()
