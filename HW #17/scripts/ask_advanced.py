"""Day 7: ask one question through any retrieval mode; the answer uses Day 6's answer().

    python -m scripts.ask_advanced "I get VPN-809 when I connect, what do I do?" --mode full
    python -m scripts.ask_advanced "And what about P3?" --previous "What is the response target for a P1 incident?" --mode full
The default mode is RAG_MODE in .env.
"""

import argparse

from app.advanced import MODES, RAG_MODE, retrieve
from app.rag import answer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--mode", default=RAG_MODE, choices=MODES)
    ap.add_argument("--previous", default=None)
    ap.add_argument("--name", default="it_policies", help="collection name")
    args = ap.parse_args()
    r = retrieve(args.question, mode=args.mode, previous=args.previous, name=args.name)
    if r["query"] != args.question:
        print(f"Searched for: {r['query']}\n")
    result = answer(r["query"], retrieve=lambda _: r["chunks"])
    print(result["answer"])
    print(
        "\nSources:",
        "; ".join(result["sources"]) if result["sources"] else "none (declined)",
    )
    print(
        f"Mode: {args.mode}   Model calls: {r['model_calls']} for retrieval + "
        f"{0 if result['declined'] and not result['sources'] else 1} for the answer"
    )


if __name__ == "__main__":
    main()
