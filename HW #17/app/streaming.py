"""Day 9: stream the chatbot's answer piece by piece, the way chat apps show text as it is written.

Finding the sources is done. Activity 2: fill in stream_answer(). Check it with tests/test_streaming.py.
"""

# Where the chunks come from (retrieve) and which search mode to use (vector, hybrid, rerank, full).
from app.advanced import RAG_MODE, retrieve
# DECLINE = the "I don't know" sentence; MIN_SCORE = how good a match must be; MODEL = which AI model;
# build_prompt = turns the question + chunks into the prompt text; llm_client = the connection to the model.
from app.rag import DECLINE, MIN_SCORE, MODEL, build_prompt, llm_client  # noqa: F401  (you will need it)


def find_sources(question: str, mode: str = RAG_MODE, min_score: float = MIN_SCORE, retriever=retrieve) -> dict:
    """The chunks to answer from (the same rules as answer() on Day 6) and how to show them.
    Returns {"query": the text that was searched, "kept": chunks, "sources": ["<source>, page <page>", ...]}."""
    # Step 1: search the documents for the best-matching chunks.
    r = retriever(question, mode=mode)
    # Step 2: keep only chunks whose score is high enough; weak matches are thrown away.
    kept = [c for c in r["chunks"] if c["score"] >= min_score]
    # Step 3: hand back the chunks to answer from, plus labels like "vpn.pdf, page 1" to show the user.
    return {
        "query": r["query"],
        "kept": kept,
        "sources": [f"{c['source']}, page {c['page']}" for c in kept],
    }


def stream_answer(question: str, kept: list, client=None, model: str = MODEL):
    """Yield the answer text piece by piece.

    Rules (tests/test_streaming.py checks each one):
    - if kept is empty: yield DECLINE once and stop, WITHOUT calling the model
    - otherwise call the model ONCE (client defaults to llm_client(); use the model given) with
      temperature=0, stream=True and
      messages=[{"role": "user", "content": build_prompt(question, kept)}]
    - the reply is a stream of chunks: for each chunk, the new text is chunk.choices[0].delta.content
    - skip chunks with no choices, and pieces that are None or ""; yield every other piece
    """
    # Case 1: no good chunks.
    if not kept:  # nothing relevant was found: decline in code, without calling the model
        yield DECLINE
        return
    # Case 2: there are chunks. Use the given client (tests pass a fake one), else the real one.
    client = client or llm_client()
    # stream=True: the model sends its answer in small pieces while it is still writing.
    stream = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": build_prompt(question, kept)}],
        temperature=0,
        stream=True,
    )
    # Pass each piece on the moment it arrives (that is what `yield` does), so the page can show it live.
    for chunk in stream:
        if not chunk.choices:  # some chunks carry no choices (for example the final usage chunk)
            continue
        piece = chunk.choices[0].delta.content
        if piece:  # skips None and ""
            yield piece
