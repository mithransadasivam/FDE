"""Day 6, Activity 3: ask one question and get an answer with its sources.

python -m scripts.ask "What is the minimum password length?"
"""

import argparse
from functools import partial

from app.indexing import search
from app.rag import answer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--name", default="it_policies", help="collection name")
    args = ap.parse_args()
    result = answer(args.question, retrieve=partial(search, name=args.name))
    print(result["answer"])
    print(
        "\nSources:",
        "; ".join(result["sources"]) if result["sources"] else "none (declined)",
    )


if __name__ == "__main__":
    main()
