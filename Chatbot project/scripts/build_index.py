"""Rebuild the vector index from scratch and print the total chunk count.

Run: .venv/Scripts/python.exe -m scripts.build_index
Count only (no embedding): .venv/Scripts/python.exe -m scripts.build_index --count
Read scanned pages first (vision model, saved so it is only paid once): .venv/Scripts/python.exe -m scripts.build_index --transcribe
"""
import sys

from app.chunker import chunk_document
from app.config import CHROMA_DIR, COLLECTION_NAME, DOCS_DIR
from app.embeddings import EmbeddingError, embed_documents
from app.loader import load_documents
from app.uploads import read_unread_pages
from app.store import build_index, count_chunks


def main() -> int:
    if "--count" in sys.argv:
        try:
            print(f"Collection '{COLLECTION_NAME}' holds {count_chunks()} chunks (read from disk, no embedding).")
        except ValueError as err:
            print(err)
            return 1
        return 0

    if "--transcribe" in sys.argv:
        from app.llm import LLMError
        from app.scanned import estimate, pages_to_read
        waiting = {pdf.name: pages_to_read(pdf) for pdf in sorted(DOCS_DIR.glob("*.pdf"))}
        waiting = {name: pages for name, pages in waiting.items() if pages}
        total_pages = sum(len(pages) for pages in waiting.values())
        if total_pages:
            plan = estimate(total_pages)
            print(f"Reading {total_pages} scanned page(s) with the vision model: {plan['calls']} calls, about ${plan['cost_usd']:.3f}.")
            try:
                result = read_unread_pages(DOCS_DIR, progress=lambda n, of: print(f"  read page {n} of {of}", flush=True))
            except LLMError as err:
                print(f"ERROR: {err}")
                return 1
            if result["failed"]:
                print(f"ERROR: the vision model stopped at {result['failed'][0]} page {result['failed'][1]}. What was read is saved; run again to continue.")
                return 1
        else:
            print("No scanned pages are waiting to be read.")

    chunks, waiting_docs = [], []
    for doc in load_documents(DOCS_DIR):
        chunks.extend(chunk_document(doc))
        if doc["page_kinds"].count("picture"):
            waiting_docs.append((doc["source"], doc["page_kinds"].count("picture")))
    for name, count in waiting_docs:
        print(f"WARNING: {name} has {count} scanned page(s) that have not been read, so they are not in the index. Run with --transcribe.")
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
