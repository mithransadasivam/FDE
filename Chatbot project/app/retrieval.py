"""One entry point for retrieval: pick the mode, get the chunks.

The chatbot and the evaluation both call these functions, so they always use the same mode.

Modes:
  vector  meaning-based search only (the original Part 1 search)
  hybrid  keyword + meaning-based search, fused
  rerank  hybrid candidates, then the model judges them (1 model call)
  full    rewrite the question into a standalone search query, then hybrid, then rerank (2 model calls)
  smart   vector search, but a question that looks like a follow-up is first rewritten using the previous question into two
          queries (the standalone question and a policy-style one); the first query's results are kept and up to 2 extra chunks
          from the second are added (1 model call only for follow-ups, none for a standalone question). Added in the Day 8
          exercise; the second query was added later to fix CTX-03.

Only "full" and "smart" use the previous question; the other modes search for the question as typed.
"""
from app.config import FOLLOW_UP_EXTRA_CHUNKS, RERANK_CANDIDATES, RETRIEVAL_MODE, RETRIEVAL_MODES, TOP_K
from app.followup import looks_like_follow_up
from app.hybrid import hybrid_search
from app.rerank import rerank
from app.retriever import search
from app.language import is_english
from app.rewrite import rewrite_queries, rewrite_query, to_english_query

MODES = RETRIEVAL_MODES
MODEL_CALLS = {"vector": 0, "hybrid": 0, "rerank": 1, "full": 2, "smart": 1}  # most model calls one retrieval makes ("smart": only for a follow-up)


def add_extras(primary: list[dict], secondary: list[dict], extra: int) -> list[dict]:
    """The first query's results exactly as they are, plus up to `extra` more chunks from the second query that are not already there.

    Keeping the first results untouched means the second query can only ADD evidence, never push out what already worked.
    """
    chunks = list(primary)
    seen = {(c["source"], c["page"], c.get("chunk")) for c in chunks}
    for chunk in secondary:
        if len(chunks) >= len(primary) + extra:
            break
        key = (chunk["source"], chunk["page"], chunk.get("chunk"))
        if key not in seen:
            chunks.append(chunk)
            seen.add(key)
    return chunks


def retrieve_detailed(question: str, k: int = TOP_K, mode: str | None = None, previous_question: str = "", english_query: str | None = None) -> dict:
    """Return {"chunks": top k chunks, "searched_for": the text that was actually searched for}."""
    mode = mode or RETRIEVAL_MODE
    if mode == "vector":
        return {"chunks": search(question, k), "searched_for": question}
    if mode == "hybrid":
        return {"chunks": hybrid_search(question, k), "searched_for": question}
    if mode == "rerank":
        return {"chunks": rerank(question, hybrid_search(question, RERANK_CANDIDATES), k), "searched_for": question}
    if mode == "smart":
        if not is_english(question):
            # the documents are English: search with an English query (1 model call, unless the caller already made it)
            queries = [english_query or to_english_query(question, previous_question)]
        elif previous_question and looks_like_follow_up(question):
            queries = rewrite_queries(question, previous_question)  # 1 or 2 queries from ONE model call
        else:
            queries = [question]
        chunks = search(queries[0], k)
        if len(queries) > 1:
            chunks = add_extras(chunks, search(queries[1], k + 2 * FOLLOW_UP_EXTRA_CHUNKS), FOLLOW_UP_EXTRA_CHUNKS)
        return {"chunks": chunks, "searched_for": " | ".join(queries)}
    if mode == "full":
        query = rewrite_query(question, previous_question)
        return {"chunks": rerank(query, hybrid_search(query, RERANK_CANDIDATES), k), "searched_for": query}
    raise ValueError(f"Unknown retrieval mode '{mode}'. Choose one of: {', '.join(MODES)}")


def retrieve(question: str, k: int = TOP_K, mode: str | None = None, previous_question: str = "") -> list[dict]:
    """Return the top `k` chunks for a question using `mode` (default: the setting in config)."""
    return retrieve_detailed(question, k, mode, previous_question)["chunks"]
