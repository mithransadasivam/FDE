"""Rebuild the vector index from scratch and print the total chunk count.

Run: .venv/Scripts/python.exe -m scripts.build_index
Count only (no embedding): .venv/Scripts/python.exe -m scripts.build_index --count
"""
import sys

from app.chunker import chunk_document
from app.config import CHROMA_DIR, COLLECTION_NAME, DOCS_DIR
from app.embeddings import EmbeddingError, embed_documents
from app.loader import load_documents
from app.store import build_index, count_chunks


def main() -> int:
    if "--count" in sys.argv:
        try:
            print(f"Collection '{COLLECTION_NAME}' holds {count_chunks()} chunks (read from disk, no embedding).")
        except ValueError as err:
            print(err)
            return 1
        return 0

    chunks = []
    for doc in load_documents(DOCS_DIR):
        chunks.extend(chunk_document(doc))
    print(f"Embedding {len(chunks)} chunks with Ollama...")
    try:
        total = build_index(chunks, embed_documents)
    except EmbeddingError as err:
        print(f"ERROR: {err}")
        return 1
    print(f"Done. Collection '{COLLECTION_NAME}' now holds {total} chunks, saved in {CHROMA_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
