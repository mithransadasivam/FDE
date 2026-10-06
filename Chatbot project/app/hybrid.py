"""Hybrid search: keyword search (BM25) plus meaning-based search, merged by reciprocal rank fusion.

Meaning-based search is good at paraphrases but can blur exact codes and names
(VPN-806 vs VPN-815). Keyword search is the opposite. Fusing the two lists by
position keeps what each finds.
"""
import re

import numpy as np
from rank_bm25 import BM25Okapi

from app.config import CHROMA_DIR, COLLECTION_NAME, HYBRID_CANDIDATES, TOP_K
from app.embeddings import embed_query
from app.store import get_collection

# Very common words carry no signal for keyword search. "not" and "no" are kept: they change meaning.
STOPWORDS = frozenset(
    "a an the and or of to in on at is are was were be been it its my me i you your we our do does did "
    "how what when who why can could should would for with from this that if so as by have has get got "
    "than then there these those into about".split()
)
# A token is letters/digits joined by - _ or . so codes (VPN-809), versions (5.2) and
# addresses (reset.northwind.example) stay in one piece. A trailing full stop is not part of it.
TOKEN = re.compile(r"[a-z0-9]+(?:[-_.][a-z0-9]+)*")
RRF_C = 60  # the usual constant for reciprocal rank fusion


def tokenize(text: str) -> list[str]:
    """Lower-case, split into tokens (keeping codes whole) and drop very common words."""
    return [t for t in TOKEN.findall(text.lower()) if t not in STOPWORDS]


def reciprocal_rank_fusion(rankings: list[list[str]], c: int = RRF_C) -> list[str]:
    """Merge several best-first lists of ids into one.

    Each id scores the sum of 1 / (c + position) over the lists it appears in (position
    starts at 1), so ids that are high in several lists win. Ties keep the order in which
    the ids were first seen. Duplicates inside one list count once, at their best position.
    The input lists are not changed.
    """
    scores: dict[str, float] = {}
    first_seen: dict[str, int] = {}
    for ranking in rankings:
        seen_here = set()
        for position, item in enumerate(ranking, start=1):
            if item in seen_here:
                continue
            seen_here.add(item)
            scores[item] = scores.get(item, 0.0) + 1.0 / (c + position)
            first_seen.setdefault(item, len(first_seen))
    return sorted(scores, key=lambda item: (-scores[item], first_seen[item]))


def keyword_rank(question: str, ids: list[str], texts: list[str], limit: int) -> list[str]:
    """Ids of the chunks that best match the question's words (BM25), best first.

    Chunks sharing no word with the question are left out, so an empty question or a
    question of only common words gives an empty list.
    """
    query = tokenize(question)
    corpus = [tokenize(t) for t in texts]
    if not query or not any(corpus):
        return []
    scores = BM25Okapi(corpus).get_scores(query)
    order = sorted(range(len(ids)), key=lambda i: (-scores[i], i))
    return [ids[i] for i in order if scores[i] > 0][:limit]


def _cosine(a, b) -> float:
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    return float(a @ b / denominator) if denominator else 0.0


def hybrid_search(question: str, k: int = TOP_K, candidates: int = HYBRID_CANDIDATES,
                  embed_fn=embed_query, path=CHROMA_DIR, name: str = COLLECTION_NAME) -> list[dict]:
    """Top `k` chunks from meaning-based and keyword search fused together, best first.

    Each result is {text, source, page, chunk, score, found_by}. `score` is always the
    cosine similarity to the question (also for chunks only the keyword search found), so
    the minimum-score guard works exactly as in vector mode. `found_by` is "vector",
    "keyword" or "both". A blank question gives []; a missing index raises ValueError.
    """
    if k <= 0:
        raise ValueError("k must be greater than 0")
    question = question.strip()
    if not question:
        return []
    collection = get_collection(path, name)
    total = collection.count()
    if total == 0:
        return []

    query_vector = embed_fn(question)
    found = collection.query(
        query_embeddings=[query_vector], n_results=min(candidates, total),
        include=["documents", "metadatas", "distances"],
    )
    vector_ids = found["ids"][0]
    chunks = {}
    for cid, text, meta, dist in zip(vector_ids, found["documents"][0], found["metadatas"][0], found["distances"][0]):
        chunks[cid] = {"text": text, "source": meta["source"], "page": meta["page"], "chunk": meta["chunk"],
                       "score": round(1.0 - dist, 4)}

    everything = collection.get(include=["documents", "metadatas"])
    keyword_ids = keyword_rank(question, everything["ids"], everything["documents"], candidates)

    fused = reciprocal_rank_fusion([vector_ids, keyword_ids])[:k]

    # Chunks only the keyword search found still need a similarity score for the guard.
    missing = [cid for cid in fused if cid not in chunks]
    if missing:
        stored = collection.get(ids=missing, include=["documents", "metadatas", "embeddings"])
        for cid, text, meta, vec in zip(stored["ids"], stored["documents"], stored["metadatas"], stored["embeddings"]):
            chunks[cid] = {"text": text, "source": meta["source"], "page": meta["page"], "chunk": meta["chunk"],
                           "score": round(_cosine(query_vector, vec), 4)}

    results = []
    for cid in fused:
        in_vector, in_keyword = cid in vector_ids, cid in keyword_ids
        results.append({**chunks[cid], "found_by": "both" if in_vector and in_keyword else "vector" if in_vector else "keyword"})
    return results
