"""Day 7: measure retrieval on its own, before the model writes an answer.

A test question "hits" when one of the retrieved chunks comes from the expected document
and contains the evidence: a short phrase copied from that document that answers the question.
Loading the test set and summarising the results are done.
Activity 1: fill in score_question(). Check it with tests/test_retrieval_eval.py.
"""

import csv


def normalise(text: str) -> str:
    """Lower case, with every run of spaces and line breaks turned into one space."""
    return " ".join(text.lower().split())


def load_test_set(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def score_question(results, expected_source: str, evidence: str, k: int = 4) -> dict:
    """TODO (Activity 1): where did the right chunk come in the results?

    results is a list of chunks, best first. Each chunk is a dict with at least
    "source" (the file name) and "text".
    Rules (tests/test_retrieval_eval.py checks each one):
    - a chunk matches when its "source" equals expected_source AND
      normalise(evidence) appears inside normalise(chunk["text"])
    - rank is the position of the FIRST matching chunk, counting from 1;
      None if no chunk matches
    - hit is True when there is a rank and it is k or better (rank <= k)
    - rr (reciprocal rank) is 1 / rank, or 0.0 when there is no rank
    Return {"rank": rank, "hit": hit, "rr": rr}
    """
    wanted = normalise(evidence)
    rank = None
    for position, chunk in enumerate(results, start=1):
        if chunk["source"] == expected_source and wanted in normalise(chunk["text"]):
            rank = position
            break
    hit = rank is not None and rank <= k
    return {"rank": rank, "hit": hit, "rr": 1 / rank if rank else 0.0}


def summarise(rows: list[dict]) -> dict:
    """Hit rate and MRR over all rows, plus the hit rate for each kind of question.

    Each row needs "hit", "rr" and "kind".
    """
    n = len(rows)
    kinds = {}
    for r in rows:
        kinds.setdefault(r["kind"], []).append(r["hit"])
    return {
        "questions": n,
        "hit_rate": sum(r["hit"] for r in rows) / n if n else 0.0,
        "mrr": sum(r["rr"] for r in rows) / n if n else 0.0,
        "by_kind": {k: f"{sum(v)}/{len(v)}" for k, v in kinds.items()},
    }
