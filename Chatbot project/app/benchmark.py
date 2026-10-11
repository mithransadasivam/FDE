"""Speed and cost of the chatbot: percentiles over many calls, and an estimated price per question."""
import math

from app.eval_suite import load_suite

BENCHMARK_QUESTIONS = 50
# The questions come from the Quality and RAGAS cases, then the other answerable cases. Follow-ups bring their previous turn.
SOURCE_DIMENSIONS = ("quality", "ragas", "functional", "context")


def benchmark_questions(count: int = BENCHMARK_QUESTIONS) -> list[dict]:
    """`count` answerable questions: quality and RAGAS first, then others, repeating from the top if there are fewer."""
    pool = []
    for dimension in SOURCE_DIMENSIONS:
        pool += [c for c in load_suite() if c["dimension"] == dimension and c["expected_behaviour"] == "answer" and c["input"].strip()]
    if not pool:
        raise ValueError("The suite has no answerable questions to benchmark.")
    return [pool[i % len(pool)] for i in range(count)]


def percentile(values: list[float], p: float) -> float | None:
    """The p-th percentile (0 to 100) by the nearest-rank method: p95 means 95 of 100 answers are this fast or faster."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


def cost_usd(input_tokens: float, output_tokens: float, input_price: float, output_price: float) -> float:
    """Dollars for one call, from token counts and prices in dollars per million tokens."""
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


def summarize_calls(rows: list[dict], input_price: float, output_price: float, critic_input_price: float = 0.0, critic_output_price: float = 0.0) -> dict:
    """Numbers for a benchmark: p50, p95, slowest, errors, average tokens and cost per question.

    Each row is {seconds, input_tokens, output_tokens, error} and may add critic_input_tokens and critic_output_tokens (the
    self-critique reviews, priced separately). Failed calls count as errors and are left out of the timings.
    """
    good = [r for r in rows if not r.get("error")]
    seconds = [r["seconds"] for r in good if r.get("seconds") is not None]
    n = len(good)
    avg_in = sum(r.get("input_tokens", 0) for r in good) / n if n else 0.0
    avg_out = sum(r.get("output_tokens", 0) for r in good) / n if n else 0.0
    crit_in = sum(r.get("critic_input_tokens", 0) for r in good) / n if n else 0.0
    crit_out = sum(r.get("critic_output_tokens", 0) for r in good) / n if n else 0.0
    per_question = cost_usd(avg_in, avg_out, input_price, output_price) + cost_usd(crit_in, crit_out, critic_input_price, critic_output_price)
    return {
        "calls": len(rows),
        "errors": len(rows) - n,
        "p50_seconds": percentile(seconds, 50),
        "p95_seconds": percentile(seconds, 95),
        "slowest_seconds": max(seconds) if seconds else None,
        "avg_input_tokens": round(avg_in),
        "avg_output_tokens": round(avg_out),
        "avg_critic_input_tokens": round(crit_in),
        "avg_critic_output_tokens": round(crit_out),
        "cost_per_question_usd": round(per_question, 6),
        "cost_per_1000_usd": round(per_question * 1000, 2),
    }
