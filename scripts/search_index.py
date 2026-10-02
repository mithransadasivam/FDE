"""Day 6, Activity 2: show the chunks most similar to a question, with their scores.

python -m scripts.search_index "How long can a VPN session stay connected?"
"""

import argparse

from app.indexing import search


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--name", default="it_policies")
    args = ap.parse_args()
    for r in search(args.question, k=args.k, name=args.name):
        snippet = " ".join(r["text"].split())[:110]
        print(
            f"{r['score']:.3f}  {r['source']}, page {r['page']}\n       {snippet}...\n"
        )


if __name__ == "__main__":
    main()
