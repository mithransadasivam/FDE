"""Rebuild the vector index from scratch and print the total chunk count.

Run: .venv/Scripts/python.exe -m scripts.build_index
Count only (no embedding): .venv/Scripts/python.exe -m scripts.build_index --count
"""
import argparse
import sys
from pathlib import Path

from app.chunker import chunk_document
from app.config import CHROMA_DIR, COLLECTION_NAME, DOCS_DIR
from app.embeddings import EmbeddingError, embed_documents
from app.loader import load_documents
from app.store import build_index, count_chunks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", action="store_true")
    ap.add_argument("--folder", default=str(DOCS_DIR))
    ap.add_argument("--name", default=COLLECTION_NAME, help="collection name")
    args = ap.parse_args()
    name = args.name
    if args.count:
        try:
            print(f"Collection '{name}' holds {count_chunks(name=name)} chunks (read from disk, no embedding).")
        except ValueError as err:
            print(err)
            return 1
        return 0

    chunks = []
    for doc in load_documents(Path(args.folder)):
        chunks.extend(chunk_document(doc))
    print(f"Embedding {len(chunks)} chunks with Ollama...")
    try:
        total = build_index(chunks, embed_documents, name=name)
    except EmbeddingError as err:
        print(f"ERROR: {err}")
        return 1
    print(f"Done. Collection '{name}' now holds {total} chunks, saved in {CHROMA_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
