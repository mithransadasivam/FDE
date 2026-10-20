"""Run the 10 test questions through the answer function and save the results.

Run: .venv/Scripts/python.exe -m scripts.run_tests
Try another minimum score: .venv/Scripts/python.exe -m scripts.run_tests --min-score 0.6 --note "tuning"
Uses the real answer model, so questions are paced to stay under the rate limit.
"""
import argparse

from app.answer import answer, check_min_score
from app.config import MIN_SCORE
from app.embeddings import EmbeddingError
from app.evaluate import RESULTS_DIR, load_questions, run_tests, save_run, summarize
from app.llm import LLMError

PAUSE_SECONDS = 3


def _min_score(text: str) -> float:
    """argparse type: a number from 0 to 1 (rejects nan, inf and negatives)."""
    try:
        return check_min_score(float(text))
    except ValueError:
        raise argparse.ArgumentTypeError("must be a number from 0 to 1")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-score", type=_min_score, default=MIN_SCORE)
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    questions = load_questions()
    print(f"Running {len(questions)} questions with minimum score {args.min_score}...")
    try:
        rows = run_tests(questions, lambda q: answer(q, min_score=args.min_score), pause=PAUSE_SECONDS)
    except (ValueError, EmbeddingError, LLMError) as err:
        print(f"ERROR: {err}")
        return 1
    run = save_run(rows, args.min_score, note=args.note)

    for r in rows:
        mark = "OK  " if r["ok"] else "MISS"
        want = "answer" if r["should_answer"] else "decline"
        print(f"{mark} #{r['number']:<2} want {want:<7} got {r['behaviour']:<8} score {r['best_score']:.2f}  {r['question'][:55]}")
    s = summarize(rows)
    print(f"\nRun {run['run']} (min score {args.min_score}): behaviour correct {s['behaviour_correct']}/{s['total']}, "
          f"answered {s['answered_correctly']}/{s['should_answer']}, declined {s['declined_correctly']}/{s['should_decline']}, "
          f"avg {s['avg_seconds']} s")
    print(f"Saved to {RESULTS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
