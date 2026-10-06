"""Find the chunks most likely to contain the answer to a question."""
from app.config import CHROMA_DIR, COLLECTION_NAME, TOP_K
from app.embeddings import embed_query
from app.store import get_collection


def search(question: str, k: int = TOP_K, embed_fn=embed_query, path=CHROMA_DIR, name: str = COLLECTION_NAME) -> list[dict]:
    """Return the top `k` chunks, best first.

    Each result is {text, source, page, chunk, score}. The score is cosine
    similarity (1.0 = identical direction; higher is a better match). A blank
    question returns an empty list; a missing index raises ValueError.
    """
    if k <= 0:
        raise ValueError("k must be greater than 0")
    question = question.strip()
    if not question:
        return []
    collection = get_collection(path, name)
    found = collection.query(
        query_embeddings=[embed_fn(question)],
        n_results=min(k, collection.count()) or 1,
        include=["documents", "metadatas", "distances"],
    )
    results = []
    for text, meta, dist in zip(found["documents"][0], found["metadatas"][0], found["distances"][0]):
        results.append({
            "text": text,
            "source": meta["source"],
            "page": meta["page"],
            "chunk": meta["chunk"],
            "score": round(1.0 - dist, 4),
        })
    return results
