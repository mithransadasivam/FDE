"""Day 6: load documents, cut them into chunks, and store them in a vector database (Chroma).

Loading, indexing and searching are done.
Activity 2: fill in chunk_text(). Check it with tests/test_chunking.py.
"""

from pathlib import Path

import chromadb
from pypdf import PdfReader

from app.embeddings import embed_documents, embed_query

CHROMA_PATH = "data/chroma"


def load_pages(path: Path) -> list[tuple[int, str]]:
    """Return (page number, text) for each page. PDFs page by page; .txt and .md as one page."""
    if path.suffix.lower() == ".pdf":
        return [
            (i + 1, page.extract_text() or "")
            for i, page in enumerate(PdfReader(path).pages)
        ]
    return [(1, path.read_text(encoding="utf-8"))]


def chunk_text(text: str, size: int = 500, overlap: int = 100) -> list[str]:
    """TODO (Activity 2): cut text into overlapping pieces.

    Rules (tests/test_chunking.py checks each one):
    - each piece is at most `size` characters long
    - each new piece starts (size - overlap) characters after the previous one,
      so neighbouring pieces share `overlap` characters
    - strip spaces and line breaks from both ends of each piece; skip empty pieces
    - text shorter than `size` gives exactly one piece; empty text gives an empty list
    - stop once a piece reaches the end of the text
    - raise ValueError if overlap is not smaller than size
    """
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    chunks, start = [], 0
    while start < len(text):
        piece = text[start : start + size].strip()
        if piece:
            chunks.append(piece)
        if start + size >= len(text):
            break
        start += size - overlap
    return chunks


def get_collection(name: str = "it_policies", path: str = CHROMA_PATH):
    client = chromadb.PersistentClient(path=path)
    # cosine: Chroma compares vectors by angle; we supply our own embeddings
    return client.get_or_create_collection(
        name, metadata={"hnsw:space": "cosine"}, embedding_function=None
    )


def build_index(
    folder: str, name: str = "it_policies", path: str = CHROMA_PATH, client=None
) -> dict:
    """Load every .pdf, .txt and .md file in folder, chunk it, embed it and store it. Returns chunks per file."""
    chroma = chromadb.PersistentClient(path=path)
    if name in [c.name for c in chroma.list_collections()]:
        chroma.delete_collection(name)  # rebuild from scratch each time
    collection = get_collection(name, path)
    counts = {}
    for file in sorted(Path(folder).iterdir()):
        if file.suffix.lower() not in (".pdf", ".txt", ".md"):
            continue
        ids, texts, metas = [], [], []
        for page, text in load_pages(file):
            for i, chunk in enumerate(chunk_text(text)):
                ids.append(f"{file.name}:p{page}:c{i}")
                texts.append(chunk)
                metas.append({"source": file.name, "page": page, "chunk": i})
        if texts:
            collection.add(
                ids=ids,
                documents=texts,
                metadatas=metas,
                embeddings=embed_documents(texts, client).tolist(),
            )
        counts[file.name] = len(texts)
    return counts


def search(
    question: str,
    k: int = 4,
    name: str = "it_policies",
    path: str = CHROMA_PATH,
    client=None,
) -> list[dict]:
    """The k chunks most similar to the question, best first, each with its source, page and score."""
    result = get_collection(name, path).query(
        query_embeddings=[embed_query(question, client).tolist()],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
    return [
        {
            "text": doc,
            "source": meta["source"],
            "page": meta["page"],
            "score": round(1 - dist, 3),
        }
        for doc, meta, dist in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0]
        )
    ]
