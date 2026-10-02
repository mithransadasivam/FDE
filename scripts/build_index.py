"""Day 6, Activity 2: build the vector index from a folder of documents.

Claude Code runs it for you:
    python -m scripts.build_index                                  (the five IT policies)
    python -m scripts.build_index --folder data/my_docs --name my_docs   (homework)
"""

import argparse

from app.indexing import build_index


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default="data/policies")
    ap.add_argument("--name", default="it_policies", help="collection name")
    args = ap.parse_args()
    counts = build_index(args.folder, name=args.name)
    for file, n in counts.items():
        print(f"{n:4} chunks  {file}")
    print(
        f"\n{sum(counts.values())} chunks from {len(counts)} documents stored in collection '{args.name}'"
    )


if __name__ == "__main__":
    main()
