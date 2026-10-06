"""Measure retrieval on its own: does the right chunk come back, and how high up?

A chunk counts as right when it comes from the expected document AND contains the
evidence phrase (ignoring upper/lower case and line breaks).
"""
import csv
import json
import time
from pathlib import Path

from app.config import ROOT
from app.loader import load_document

RETRIEVAL_SET_FILE = ROOT / "data" / "retrieval_test_set.csv"
RETRIEVAL_RESULTS_DIR = ROOT / "data" / "retrieval_results"
KINDS = ["plain", "reworded", "exact code", "follow-up", "messy"]
COLUMNS = ["question", "previous_question", "kind", "expected_source", "evidence", "expected_answer"]
DEPTH = 10  # how many chunks are retrieved for scoring; a hit still needs rank <= k


def normalise(text: str) -> str:
    """Lower-case and collapse every run of whitespace (including line breaks) to one space."""
    return " ".join(text.lower().split())


def load_retrieval_set(path: Path = RETRIEVAL_SET_FILE) -> list[dict]:
    """Read the test set. Raises ValueError for missing columns, empty cells or an unknown kind."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or set(COLUMNS) - set(reader.fieldnames):
            raise ValueError(f"The retrieval test set must have the columns: {', '.join(COLUMNS)}")
        rows = []
        for line_no, row in enumerate(reader, start=2):
            row = {key: (row.get(key) or "").strip() for key in COLUMNS}
            for key in ("question", "kind", "expected_source", "evidence"):
                if not row[key]:
                    raise ValueError(f"Line {line_no} of {path}: '{key}' is empty")
            if row["kind"] not in KINDS:
                raise ValueError(f"Line {line_no} of {path}: unknown kind '{row['kind']}'")
            rows.append(row)
    return rows


def check_evidence(rows: list[dict], docs_dir: Path) -> list[dict]:
    """Return the rows whose evidence phrase is NOT in its expected document (empty list = all good)."""
    missing = []
    for row in rows:
        path = Path(docs_dir) / row["expected_source"]
        if not path.is_file():
            missing.append({**row, "problem": "expected document not found"})
            continue
        text = normalise(" ".join(page for _, page in load_document(path)["pages"]))
        if normalise(row["evidence"]) not in text:
            missing.append({**row, "problem": "evidence phrase not in the document"})
    return missing


def score_row(chunks: list[dict], expected_source: str, evidence: str, k: int) -> dict:
    """Score one retrieval result list.

    rank: position (1 = best) of the first chunk that is from the expected document and
    contains the evidence, or None if there is none. hit: rank is within the top k.
    rr: reciprocal rank, 1 / rank, or 0 when not found.
    """
    wanted = normalise(evidence)
    for position, chunk in enumerate(chunks, start=1):
        if chunk["source"] == expected_source and wanted in normalise(chunk["text"]):
            return {"rank": position, "hit": position <= k, "rr": 1.0 / position}
    return {"rank": None, "hit": False, "rr": 0.0}


def run_eval(rows: list[dict], retrieve, k: int, depth: int = DEPTH, pause: float = 0.0, sleep=time.sleep) -> list[dict]:
    """Run every row through `retrieve(row)` and score it.

    `retrieve` receives the whole test-set row, so a mode that rewrites follow-ups can
    use `previous_question`. It returns the chunks (best first), or a dict
    {"chunks": [...], "searched_for": "..."} when it also reports the query it used. Time is measured per row. `pause` seconds are waited between rows
    (not counted in the time) to stay under a model's rate limit.
    """
    results = []
    for number, row in enumerate(rows):
        if number and pause:
            sleep(pause)
        started = time.perf_counter()
        found = retrieve(row)
        seconds = time.perf_counter() - started
        chunks = (found["chunks"] if isinstance(found, dict) else found)[:depth]
        searched_for = found["searched_for"] if isinstance(found, dict) else row["question"]
        results.append({
            "question": row["question"],
            "previous_question": row["previous_question"],
            "kind": row["kind"],
            "expected_source": row["expected_source"],
            "evidence": row["evidence"],
            "searched_for": searched_for,
            **score_row(chunks, row["expected_source"], row["evidence"], k),
            # True when reranking could not use the model's reply and kept the original order
            "rerank_fallback": any("rerank_score" in c and c["rerank_score"] is None for c in chunks),
            "seconds": round(seconds, 3),
            "top_sources": "; ".join(f"{c['source']} p.{c['page']}" for c in chunks[:k]),
        })
    return results


def summarize(results: list[dict]) -> dict:
    """Hit rate, MRR, hits per kind and average time."""
    total = len(results)
    by_kind = {}
    for kind in KINDS:
        of_kind = [r for r in results if r["kind"] == kind]
        if of_kind:
            by_kind[kind] = {"hits": sum(r["hit"] for r in of_kind), "total": len(of_kind)}
    return {
        "questions": total,
        "hits": sum(r["hit"] for r in results),
        "hit_rate": round(sum(r["hit"] for r in results) / total, 4) if total else 0.0,
        "mrr": round(sum(r["rr"] for r in results) / total, 4) if total else 0.0,
        "by_kind": by_kind,
        "rerank_fallbacks": sum(bool(r.get("rerank_fallback")) for r in results),
        "avg_seconds": round(sum(r["seconds"] for r in results) / total, 3) if total else 0.0,
    }


def save_eval(results: list[dict], mode: str, k: int, folder: Path = RETRIEVAL_RESULTS_DIR) -> Path:
    """Save every row to <mode>.csv and the summary to <mode>.json; return the csv path."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    csv_path = folder / f"{mode}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0]) if results else ["question"])
        writer.writeheader()
        writer.writerows({key: (("'" + value) if isinstance(value, str) and value[:1] in "=+-@" and value else value)
                          for key, value in row.items()} for row in results)
    summary = {"mode": mode, "k": k, **summarize(results)}
    (folder / f"{mode}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return csv_path
