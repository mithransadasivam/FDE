"""Day 9: stream the chatbot's answer piece by piece, the way chat apps show text as it is written.

Finding the sources is done. Activity 2: fill in stream_answer(). Check it with tests/test_streaming.py.
"""

from app.advanced import RAG_MODE, retrieve
from app.rag import DECLINE, MIN_SCORE, MODEL, build_prompt, llm_client  # noqa: F401  (you will need it)


def find_sources(question: str, mode: str = RAG_MODE, min_score: float = MIN_SCORE, retriever=retrieve) -> dict:
    """The chunks to answer from (the same rules as answer() on Day 6) and how to show them.
    Returns {"query": the text that was searched, "kept": chunks, "sources": ["<source>, page <page>", ...]}."""
    r = retriever(question, mode=mode)
    kept = [c for c in r["chunks"] if c["score"] >= min_score]
    return {
        "query": r["query"],
        "kept": kept,
        "sources": [f"{c['source']}, page {c['page']}" for c in kept],
    }


def stream_answer(question: str, kept: list, client=None, model: str = MODEL):
    """TODO (Activity 2): yield the answer text piece by piece.

    Rules (tests/test_streaming.py checks each one):
    - if kept is empty: yield DECLINE once and stop, WITHOUT calling the model
    - otherwise call the model ONCE (client defaults to llm_client(); use the model given) with
      temperature=0, stream=True and
      messages=[{"role": "user", "content": build_prompt(question, kept)}]
    - the reply is a stream of chunks: for each chunk, the new text is chunk.choices[0].delta.content
    - skip chunks with no choices, and pieces that are None or ""; yield every other piece
    """
    raise NotImplementedError("TODO")
