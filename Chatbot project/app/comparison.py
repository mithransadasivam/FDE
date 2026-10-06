"""Compare the retrieval modes side by side and save the table."""
import csv
import json
from pathlib import Path

from app.config import ROOT
from app.retrieval import MODEL_CALLS
from app.retrieval_eval import KINDS, RETRIEVAL_RESULTS_DIR, summarize

COMPARISON_JSON = ROOT / "data" / "retrieval_comparison.json"
COMPARISON_CSV = ROOT / "data" / "retrieval_comparison.csv"


def build_row(mode: str, k: int, retrieval_results: list[dict], behaviour_rows: list[dict] | None = None) -> dict:
    """One row of the comparison: retrieval scores, cost, and (when measured) the Part 1 behaviour test.

    `behaviour_rows` are the rows of `app.evaluate.run_tests` for the same mode, run through the
    real answer function, so `answer_seconds` is the whole answer: retrieval plus the model writing the reply.
    """
    s = summarize(retrieval_results)
    row = {
        "mode": mode,
        "k": k,
        "questions": s["questions"],
        "hits": s["hits"],
        "hit_rate": s["hit_rate"],
        "mrr": s["mrr"],
        "by_kind": s["by_kind"],
        "retrieval_ms": round(s["avg_seconds"] * 1000),
        "retrieval_model_calls": MODEL_CALLS[mode],
        "calls_per_answer": MODEL_CALLS[mode] + 1,  # plus the call that writes the answer
        "rerank_fallbacks": s["rerank_fallbacks"],
        "behaviour_correct": None,
        "behaviour_total": None,
        "answer_seconds": None,
    }
    if behaviour_rows:
        row.update(
            behaviour_correct=sum(r["ok"] for r in behaviour_rows),
            behaviour_total=len(behaviour_rows),
            answer_seconds=round(sum(r["seconds"] for r in behaviour_rows) / len(behaviour_rows), 2),
        )
    return row


def meets_target(row: dict, target_hit_rate: float, target_seconds: float) -> bool:
    """True when the hit rate reaches the target AND a whole answer is within the time target.

    A mode whose answer time was not measured cannot be said to meet the target.
    """
    return bool(row["answer_seconds"] is not None and row["hit_rate"] >= target_hit_rate and row["answer_seconds"] <= target_seconds)


def save_comparison(rows: list[dict], json_path: Path = COMPARISON_JSON, csv_path: Path = COMPARISON_CSV) -> None:
    """Save one row per mode as JSON (everything) and CSV (flat, for a spreadsheet)."""
    json_path, csv_path = Path(json_path), Path(csv_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    columns = (["mode", "k", "questions", "hits", "hit_rate", "mrr"] + KINDS +
               ["retrieval_ms", "retrieval_model_calls", "calls_per_answer", "rerank_fallbacks",
                "behaviour_correct", "behaviour_total", "answer_seconds"])
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            flat = {key: row.get(key) for key in columns}
            for kind in KINDS:
                cell = row["by_kind"].get(kind)
                flat[kind] = f"{cell['hits']}/{cell['total']}" if cell else ""
            writer.writerow(flat)


def load_comparison(json_path: Path = COMPARISON_JSON) -> list[dict]:
    """The saved comparison rows, or [] when there is no (readable) file yet."""
    try:
        rows = json.loads(Path(json_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    needed = {"mode", "hit_rate", "mrr", "by_kind", "retrieval_ms", "calls_per_answer"}
    return [r for r in rows if isinstance(r, dict) and needed <= r.keys()] if isinstance(rows, list) else []


def load_mode_results(mode: str, folder: Path = RETRIEVAL_RESULTS_DIR) -> list[dict]:
    """The saved per-question rows of one mode (data/retrieval_results/<mode>.csv), or [] if missing."""
    try:
        with open(Path(folder) / f"{mode}.csv", newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []
