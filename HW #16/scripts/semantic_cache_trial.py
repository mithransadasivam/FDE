"""Day 16 homework, Task 3: would a semantic cache answer these pairs correctly?

A semantic cache reuses an answer when a new question is close enough in meaning to a cached one:
the cosine similarity of their embeddings is at least a threshold. Too low a threshold serves the
wrong answer ("P1" for "P2"); too high, and it is just the exact cache again.

python -m scripts.semantic_cache_trial                       (thresholds 0.80 to 0.98)
python -m scripts.semantic_cache_trial --pairs data/my_pairs.csv

Needs Ollama running (the same nomic-embed-text embeddings as the index). No chat model is called.
"""

import argparse
import csv

from app.embeddings import cosine_similarity, embed_query

PAIRS = "data/Day16_HW_Slide05_question_pairs.csv"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pairs", default=PAIRS)
    p.add_argument("--thresholds", nargs="+", type=float, default=[0.80, 0.85, 0.90, 0.95, 0.98])
    a = p.parse_args()
    with open(a.pairs, newline="", encoding="utf-8") as f:
        pairs = list(csv.DictReader(f))
    for row in pairs:
        row["similarity"] = round(cosine_similarity(embed_query(row["question_a"]), embed_query(row["question_b"])), 3)
    print(f"{'similarity':>10}  same?  pair")
    for row in sorted(pairs, key=lambda r: -r["similarity"]):
        print(f"{row['similarity']:>10}  {row['same_answer']:5}  {row['question_a'][:45]}  |  {row['question_b'][:45]}")
    print(f"\n{'threshold':>10}  {'right hits':>10}  {'wrong hits':>10}  {'missed':>7}")
    for t in a.thresholds:
        hits = [r for r in pairs if r["similarity"] >= t]
        right = sum(r["same_answer"] == "yes" for r in hits)
        wrong = len(hits) - right
        missed = sum(r["same_answer"] == "yes" for r in pairs) - right
        print(f"{t:>10}  {right:>10}  {wrong:>10}  {missed:>7}")
    print("\nA wrong hit gives a user someone else's answer. Pick the lowest threshold with no wrong hits,"
          "\nthen ask whether that is still worth having.")


if __name__ == "__main__":
    main()
