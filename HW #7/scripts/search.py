"""Retrieval only: print the top chunks for a question. No answer model is used.

Run: .venv/Scripts/python.exe -m scripts.search "How do I set up MFA on a new phone?"
"""
import sys

from app.config import TOP_K
from app.embeddings import EmbeddingError
from app.retriever import search


def main() -> int:
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        print('Usage: python -m scripts.search "your question"')
        return 1
    try:
        results = search(question, TOP_K)
    except (ValueError, EmbeddingError) as err:
        print(f"ERROR: {err}")
        return 1
    print(f"Question: {question}\n")
    for rank, r in enumerate(results, start=1):
        snippet = " ".join(r["text"].split())[:200]
        print(f"{rank}. score {r['score']:.3f}  {r['source']} · page {r['page']} · chunk {r['chunk']}")
        print(f"   {snippet}...\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
