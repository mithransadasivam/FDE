"""Run the retrieval test set for one retrieval mode and print the scores.

Run: .venv/Scripts/python.exe -m scripts.eval_retrieval --mode vector
Only retrieval is measured: no answer is written. Rows are saved to data/retrieval_results/<mode>.csv.
"""
import argparse

from app.config import TOP_K
from app.embeddings import EmbeddingError
from app.retrieval_eval import DEPTH, KINDS, load_retrieval_set, run_eval, save_eval, summarize
from app.retrieval import MODEL_CALLS, MODES, retrieve_detailed


def retrieve_for_mode(mode: str, depth: int):
    """Return a function row -> chunks for the chosen mode."""
    if mode not in MODES:
        raise ValueError(f"Unknown mode: {mode}")
    return lambda row: retrieve_detailed(row["question"], depth, mode=mode, previous_question=row["previous_question"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=MODES, default="vector")  # the chatbot uses RETRIEVAL_MODE from config
    parser.add_argument("--k", type=int, default=TOP_K, help="chunks that count (the number the chatbot puts in its prompt)")
    parser.add_argument("--pause", type=float, default=None, help="seconds between questions (default 3 per model call the mode makes: 0, 3 or 6)")
    args = parser.parse_args()
    pause = args.pause if args.pause is not None else 3.0 * MODEL_CALLS[args.mode]

    try:
        rows = load_retrieval_set()
        results = run_eval(rows, retrieve_for_mode(args.mode, max(DEPTH, args.k)), args.k, pause=pause)
    except (OSError, ValueError, EmbeddingError) as err:
        print(f"ERROR: {err}")
        return 1
    path = save_eval(results, args.mode, args.k)

    s = summarize(results)
    print(f"Mode: {args.mode}  |  k = {args.k}  |  {s['questions']} questions\n")
    for r in results:
        rank = r["rank"] if r["rank"] else "-"
        mark = "HIT " if r["hit"] else "MISS"
        print(f"{mark} rank {str(rank):<2} {r['kind']:<10} {r['question'][:60]}")
    print(f"\nHit rate @{args.k}: {s['hits']}/{s['questions']} = {s['hit_rate']:.0%}")
    print(f"MRR: {s['mrr']:.2f}")
    print("Hits by kind: " + ", ".join(f"{k} {s['by_kind'][k]['hits']}/{s['by_kind'][k]['total']}" for k in KINDS if k in s["by_kind"]))
    if MODEL_CALLS[args.mode]:
        print(f"Model calls per question: {MODEL_CALLS[args.mode]}  |  replies that could not be used (original order kept): {s['rerank_fallbacks']}")
    print(f"Average retrieval time: {s['avg_seconds'] * 1000:.0f} ms per question")
    print(f"Saved to {path.parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
