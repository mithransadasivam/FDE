"""Run every retrieval mode on the retrieval test set and compare them.

Run: .venv/Scripts/python.exe -m scripts.compare_modes
For each mode this measures: hit rate, MRR, hits by kind, retrieval time, model calls, and
(unless --skip-behaviour) the Part 1 answer-or-decline test through the real answer function,
so the answer time is the whole answer. Modes that call the model are paced to stay under
the rate limit, so a full run takes several minutes.
Saves data/retrieval_comparison.csv and .json and one data/retrieval_results/<mode>.csv per mode.
"""
import argparse

from app.answer import answer
from app.comparison import COMPARISON_CSV, build_row, meets_target, save_comparison
from app.config import TARGET_HIT_RATE, TARGET_SECONDS, TOP_K
from app.embeddings import EmbeddingError
from app.evaluate import load_questions, run_tests
from app.llm import LLMError
from app.retrieval import MODEL_CALLS, MODES, retrieve, retrieve_detailed
from app.retrieval_eval import DEPTH, load_retrieval_set, run_eval, save_eval

PAUSE_PER_CALL = 3.0  # seconds between questions, per model call a question makes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    parser.add_argument("--k", type=int, default=TOP_K)
    parser.add_argument("--skip-behaviour", action="store_true", help="skip the Part 1 answer-or-decline test (faster, no answer times)")
    args = parser.parse_args()

    try:
        test_set = load_retrieval_set()
        behaviour_questions = [] if args.skip_behaviour else load_questions()
    except (OSError, ValueError) as err:
        print(f"ERROR: {err}")
        return 1

    rows = []
    for mode in args.modes:
        print(f"\n=== {mode} ===", flush=True)
        try:
            results = run_eval(
                test_set,
                lambda row: retrieve_detailed(row["question"], max(DEPTH, args.k), mode=mode, previous_question=row["previous_question"]),
                args.k, pause=PAUSE_PER_CALL * MODEL_CALLS[mode])
            save_eval(results, mode, args.k)
            behaviour = None
            if behaviour_questions:
                behaviour = run_tests(
                    behaviour_questions,
                    lambda q: answer(q, retriever=lambda question, k: retrieve(question, k, mode=mode), k=args.k),
                    pause=PAUSE_PER_CALL * (MODEL_CALLS[mode] + 1))
        except (OSError, ValueError, EmbeddingError, LLMError) as err:
            print(f"ERROR in mode {mode}: {err}")
            return 1
        row = build_row(mode, args.k, results, behaviour)
        rows.append(row)
        print(f"hit rate {row['hit_rate']:.0%}  MRR {row['mrr']:.2f}  retrieval {row['retrieval_ms']} ms  "
              f"behaviour {row['behaviour_correct']}/{row['behaviour_total']}  answer {row['answer_seconds']} s", flush=True)

    save_comparison(rows)
    print(f"\n{'mode':<8}{'hit@' + str(args.k):>7}{'MRR':>6}{'retr ms':>9}{'calls':>7}{'behav':>7}{'answer s':>10}  "
          f"meets target (>= {TARGET_HIT_RATE:.0%}, <= {TARGET_SECONDS:g} s)")
    for r in rows:
        behav = f"{r['behaviour_correct']}/{r['behaviour_total']}" if r["behaviour_total"] else "-"
        secs = f"{r['answer_seconds']:.2f}" if r["answer_seconds"] is not None else "-"
        print(f"{r['mode']:<8}{r['hit_rate']:>7.0%}{r['mrr']:>6.2f}{r['retrieval_ms']:>9}{r['calls_per_answer']:>7}{behav:>7}{secs:>10}  "
              f"{'YES' if meets_target(r, TARGET_HIT_RATE, TARGET_SECONDS) else 'no'}")
    print(f"\nSaved to {COMPARISON_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
