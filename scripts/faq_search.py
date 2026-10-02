"""Day 6, Activity 1: semantic search over the IT FAQ, with numpy only.

Ready to run once cosine_similarity() is done. Claude Code runs it for you:
    python -m scripts.faq_search "my laptop wifi keeps disconnecting"
With no question, it runs three example questions.
"""

import csv
import sys

from app.embeddings import cosine_similarity, embed_documents, embed_query

FAQ = "data/Day06_Slide10_it_faq.csv"
EXAMPLES = [
    "my laptop wifi keeps disconnecting",
    "how do I get into the finance shared folder",
    "what is for lunch today",
]


def words(text):
    return {w.strip("?.,!").lower() for w in text.split()}


def main():
    with open(FAQ, newline="", encoding="utf-8") as f:
        faq = list(csv.DictReader(f))
    vectors = embed_documents(
        [row["question"] for row in faq]
    )  # one vector per FAQ question
    print(
        f"Embedded {len(faq)} FAQ questions; each vector has {vectors.shape[1]} numbers.\n"
    )

    for question in sys.argv[1:] or EXAMPLES:
        q = embed_query(question)
        scored = sorted(
            ((cosine_similarity(q, v), row) for v, row in zip(vectors, faq)),
            key=lambda pair: pair[0],
            reverse=True,
        )
        print(f'Question: "{question}"')
        for score, row in scored[:3]:
            shared = len(words(question) & words(row["question"]))
            print(f"  {score:.3f}  {row['question']:<48} words in common: {shared}")
        print(f"  -> {scored[0][1]['answer']}\n")


if __name__ == "__main__":
    main()
