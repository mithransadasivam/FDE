"""Print how many chunks each document produced; flag any that produced none.

Run: .venv/Scripts/python.exe -m scripts.chunk_report
"""
from app.chunker import chunk_document
from app.config import CHUNK_OVERLAP, CHUNK_SIZE, DOCS_DIR
from app.loader import load_documents


def main() -> int:
    docs = load_documents(DOCS_DIR)
    print(f"Folder: {DOCS_DIR}  |  chunk size {CHUNK_SIZE}, overlap {CHUNK_OVERLAP}\n")
    print(f"{'Document':<40}{'Type':<10}{'Pages':>6}{'Chunks':>8}  Status")
    total = empty = 0
    for doc in docs:
        n = len(chunk_document(doc))
        total += n
        if n == 0:
            empty += 1
            reason = doc["warning"] or "no readable text (scanned image or empty file?)"
            status = f"** NO CHUNKS: {reason}"
        else:
            status = "ok"
        print(f"{doc['source']:<40}{doc['type']:<10}{len(doc['pages']):>6}{n:>8}  {status}")
    print(f"\n{len(docs)} documents, {total} chunks, {empty} with no chunks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
