"""Day 7: one retrieve() for every pipeline you build today, chosen by its mode.

    vector  Day 6's search on its own (the baseline)
    hybrid  vector + keyword search, combined with reciprocal rank fusion   (Activity 2)
    rerank  hybrid, then the model reranks the candidates                   (Activity 3)
    full    the query is rewritten first, then hybrid + rerank              (Activity 4)

Ready to use: nothing to fill in here.
"""

import os

from dotenv import load_dotenv

from app.hybrid import hybrid_search, vector_search
from app.indexing import CHROMA_PATH
from app.rerank import rerank
from app.rewrite import rewrite_query

load_dotenv()
MODES = ["vector", "hybrid", "rerank", "full"]
RAG_MODE = os.getenv("RAG_MODE", "vector")
CANDIDATES = int(os.getenv("RERANK_CANDIDATES", "10"))


def retrieve(
    question: str,
    mode: str = RAG_MODE,
    previous: str | None = None,
    k: int = 4,
    candidates: int = CANDIDATES,
    name: str = os.getenv("COLLECTION_NAME", "it_policies"),  # set COLLECTION_NAME=my_docs for my index
    path: str = CHROMA_PATH,
    embed_client=None,
    llm=None,
) -> dict:
    """Returns {"query": the text that was searched, "chunks": the best k chunks,
    "model_calls": how many chat-model calls retrieval needed}."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    query, calls = question, 0
    if mode == "full":
        query, calls = rewrite_query(question, previous, client=llm), 1
    if mode == "vector":
        chunks = vector_search(query, k, name, path, embed_client)
    elif mode == "hybrid":
        chunks = hybrid_search(query, k, candidates, name, path, embed_client)
    else:
        wide = hybrid_search(query, candidates, candidates, name, path, embed_client)
        chunks = rerank(query, wide, top_n=k, client=llm)
        calls += 1 if wide else 0
    return {"query": query, "chunks": chunks, "model_calls": calls}
