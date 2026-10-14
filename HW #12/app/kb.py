"""Knowledge-base status and rebuild, shared by the app (and testable without it)."""
from pathlib import Path

from app.chunker import chunk_document
from app.config import CHROMA_DIR, DOCS_DIR
from app.embeddings import embed_documents
from app.loader import load_documents
from app.store import build_index, count_chunks


def overview(docs_dir: Path = DOCS_DIR, chroma: Path = CHROMA_DIR) -> dict:
    """Describe the documents and the saved index.

    Returns {rows, documents, readable, chunks, indexed_chunks, state}. `state` is
    "ready" (index matches the documents), "missing" (never built) or
    "out of date" (index and documents disagree, so a rebuild is needed).
    """
    docs = load_documents(docs_dir)
    sizes = [(d, len(chunk_document(d))) for d in docs]
    total = sum(n for _, n in sizes)
    try:
        indexed = count_chunks(chroma)
    except ValueError:
        indexed = None
    if indexed is None:
        state = "missing"
    elif indexed == total:
        state = "ready"
    else:
        state = "out of date"

    rows = []
    for doc, n in sizes:
        if n == 0:
            status = doc["warning"] or "0 chunks: no readable text"
        else:
            status = "Indexed" if state == "ready" else "Not indexed"
        rows.append({"Document": doc["source"], "Type": doc["type"], "Pages": len(doc["pages"]), "Chunks": n, "Status": status})
    return {
        "rows": rows,
        "documents": len(docs),
        "readable": sum(1 for _, n in sizes if n),
        "chunks": total,
        "indexed_chunks": indexed,
        "state": state,
    }


def rebuild(docs_dir: Path = DOCS_DIR, chroma: Path = CHROMA_DIR, embed_fn=embed_documents) -> int:
    """Rebuild the index from scratch and return the number of chunks stored."""
    chunks = []
    for doc in load_documents(docs_dir):
        chunks.extend(chunk_document(doc))
    return build_index(chunks, embed_fn, chroma)
