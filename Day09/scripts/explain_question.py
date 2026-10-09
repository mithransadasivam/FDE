"""Day 7: show what each retrieval mode found for one question, side by side.
Use it to find out WHY a question was missed.

    python -m scripts.explain_question "What does error VPN-809 mean?"
    python -m scripts.explain_question "And what about P3?" --previous "What is the response target for a P1 incident?"
    python -m scripts.explain_question "..." --name my_docs --modes vector hybrid   (homework)
"""

import argparse

from app.advanced import MODES, retrieve


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--previous", default=None)
    ap.add_argument("--name", default="it_policies", help="collection name")
    ap.add_argument("--modes", nargs="+", default=MODES, choices=MODES)
    args = ap.parse_args()
    for mode in args.modes:
        r = retrieve(args.question, mode=mode, previous=args.previous, name=args.name)
        print(
            f"=== {mode}"
            + (
                f"   (searched for: {r['query']})"
                if r["query"] != args.question
                else ""
            )
        )
        for i, c in enumerate(r["chunks"], 1):
            extra = f"  judged {c['rerank_score']:g}/10" if "rerank_score" in c else ""
            print(
                f"  {i}. {c['source']}, page {c['page']}   similarity {c['score']:.2f}{extra}"
            )
            print(f"     {' '.join(c['text'].split())[:100]}...")
        print()


if __name__ == "__main__":
    main()
