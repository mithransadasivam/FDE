"""One entry point for retrieval: pick the mode, get the chunks.

The chatbot and the evaluation both call these functions, so they always use the same mode.

Modes:
  vector  meaning-based search only (the original Part 1 search)
  hybrid  keyword + meaning-based search, fused
  rerank  hybrid candidates, then the model judges them (1 model call)
  full    rewrite the question into a standalone search query, then hybrid, then rerank (2 model calls)

Only "full" uses the previous question; the other modes search for the question as typed.
"""
from app.config import RERANK_CANDIDATES, RETRIEVAL_MODE, RETRIEVAL_MODES, TOP_K
from app.hybrid import hybrid_search
from app.rerank import rerank
from app.retriever import search
from app.rewrite import rewrite_query

MODES = RETRIEVAL_MODES
MODEL_CALLS = {"vector": 0, "hybrid": 0, "rerank": 1, "full": 2}  # model calls one retrieval makes (when it finds any chunks)


def retrieve_detailed(question: str, k: int = TOP_K, mode: str | None = None, previous_question: str = "") -> dict:
    """Return {"chunks": top k chunks, "searched_for": the text that was actually searched for}."""
    mode = mode or RETRIEVAL_MODE
    if mode == "vector":
        return {"chunks": search(question, k), "searched_for": question}
    if mode == "hybrid":
        return {"chunks": hybrid_search(question, k), "searched_for": question}
    if mode == "rerank":
        return {"chunks": rerank(question, hybrid_search(question, RERANK_CANDIDATES), k), "searched_for": question}
    if mode == "full":
        query = rewrite_query(question, previous_question)
        return {"chunks": rerank(query, hybrid_search(query, RERANK_CANDIDATES), k), "searched_for": query}
    raise ValueError(f"Unknown retrieval mode '{mode}'. Choose one of: {', '.join(MODES)}")


def retrieve(question: str, k: int = TOP_K, mode: str | None = None, previous_question: str = "") -> list[dict]:
    """Return the top `k` chunks for a question using `mode` (default: the setting in config)."""
    return retrieve_detailed(question, k, mode, previous_question)["chunks"]
