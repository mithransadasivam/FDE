"""Day 7: hybrid search = meaning-based (vector) search + keyword (BM25) search, combined.

vector_search() and keyword_search() are done. hybrid_search() is done once your
function works.
Activity 2: fill in reciprocal_rank_fusion(). Check it with tests/test_fusion.py.
"""

import re

from rank_bm25 import BM25Okapi

from app.embeddings import cosine_similarity, embed_query
from app.indexing import CHROMA_PATH, get_collection


# Very common words carry no meaning for search, so keyword search ignores them
STOPWORDS = set(
    "a an and are as at be by can do does for from how i if in is it me my of on or "
    "so that the this to was what when where which who why will with you your".split()
)


def tokenize(text: str) -> list[str]:
    """Lower-case words without stop words. A code such as VPN-809 is kept whole and
    also split into its parts (vpn, 809), so a search for 809 alone still finds it."""
    words = []
    for w in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower()):
        if w in STOPWORDS:
            continue
        words.append(w)
        if "-" in w:
            words.extend(w.split("-"))
    return words


def _chunk(id_, doc, meta, score):
    return {
        "id": id_,
        "text": doc,
        "source": meta["source"],
        "page": meta["page"],
        "score": round(score, 3),
    }


def vector_search(
    question: str,
    k: int = 4,
    name: str = "it_policies",
    path: str = CHROMA_PATH,
    client=None,
) -> list[dict]:
    """Day 6's search, plus each chunk's id: the k chunks closest in meaning, best first."""
    result = get_collection(name, path).query(
        query_embeddings=[list(embed_query(question, client))],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
    return [
        _chunk(i, d, m, 1 - dist)
        for i, d, m, dist in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
        )
    ]


def keyword_search(
    question: str,
    k: int = 4,
    name: str = "it_policies",
    path: str = CHROMA_PATH,
) -> list[dict]:
    """BM25 keyword search over every stored chunk: the k best keyword matches, best first.

    Chunks that share no words with the question are left out. "score" here is the BM25
    score, which is not on the same scale as a similarity score.
    """
    stored = get_collection(name, path).get(include=["documents", "metadatas"])
    if not stored["ids"]:
        return []
    bm25 = BM25Okapi([tokenize(d) for d in stored["documents"]])
    scores = bm25.get_scores(tokenize(question))
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return [
        _chunk(
            stored["ids"][i], stored["documents"][i], stored["metadatas"][i], scores[i]
        )
        for i in order[:k]
        if scores[i] > 0
    ]


def reciprocal_rank_fusion(*ranked_lists, k: int = 60) -> list[dict]:
    """TODO (Activity 2): combine several ranked lists of chunks into one list.

    Each list is best first, and every chunk has an "id".
    Rules (tests/test_fusion.py checks each one):
    - a chunk at position p in a list (counting from 1) earns 1 / (k + p) from that list
    - a chunk's fused score is the sum of what it earns from every list it appears in
    - return each chunk once, as a copy of the first version of it you meet, with a new
      key "rrf" holding its fused score
    - sort by "rrf", highest first; chunks with equal scores keep the order you met them in
    - do not change the lists or the chunks you were given
    """
    scores, first = {}, {}
    for ranked in ranked_lists:
        for position, chunk in enumerate(ranked, start=1):
            id_ = chunk["id"]
            if id_ not in first:
                first[id_] = chunk
            scores[id_] = scores.get(id_, 0.0) + 1 / (k + position)
    fused = [{**first[id_], "rrf": scores[id_]} for id_ in first]
    return sorted(fused, key=lambda c: c["rrf"], reverse=True)  # stable: ties keep first-met order


def hybrid_search(
    question: str,
    k: int = 4,
    candidates: int = 10,
    name: str = "it_policies",
    path: str = CHROMA_PATH,
    client=None,
) -> list[dict]:
    """Take `candidates` chunks from each search, fuse them, and keep the best k.

    "score" is set to every chunk's similarity to the question, so the Day 6 minimum-score
    guard in answer() still works.
    """
    vec = vector_search(question, candidates, name, path, client)
    kw = keyword_search(question, candidates, name, path)
    fused = reciprocal_rank_fusion(vec, kw)[:k]
    similarity = {c["id"]: c["score"] for c in vec}
    missing = [c["id"] for c in fused if c["id"] not in similarity]
    if missing:  # keyword-only chunks: work out their similarity too
        q = embed_query(question, client)
        got = get_collection(name, path).get(ids=missing, include=["embeddings"])
        for id_, e in zip(got["ids"], got["embeddings"]):
            similarity[id_] = round(cosine_similarity(q, e), 3)
    for c in fused:
        c["score"] = similarity[c["id"]]
    return fused
