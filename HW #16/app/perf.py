"""Day 16: what an answer costs, and how long it takes.

Done: PRICES, estimate_tokens() and summarise_extra().
Activity 1: fill in request_cost(). Check it with tests/test_costs.py.
Activity 3: fill in measure_stream(). Check it with tests/test_measure_stream.py.
Homework, Task 1: fill in monthly_cost(). Check it with tests/test_monthly_cost.py.
"""

import time

# US dollars per million tokens, input (the prompt) and output (the answer). Output tokens cost
# several times more than input tokens. Illustrative: check each model's page on OpenRouter.
# A model you serve yourself (ollama/...) has no price per token: you pay for the machine instead.
PRICES = {
    "anthropic/claude-haiku-4.5": {"input": 1.00, "output": 5.00},
    "openai/gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "deepseek/deepseek-chat": {"input": 0.2574, "output": 1.0287},  # OpenRouter, 2026-10-20
    # The fake chatbot (CHAT_FAKE=1) costs nothing
    "fake-primary": {"input": 0.0, "output": 0.0},
    "fake-fallback": {"input": 0.0, "output": 0.0},
    "fake-small": {"input": 0.0, "output": 0.0},
}


def estimate_tokens(text: str) -> int:
    """About four characters per token in English: good enough when a server reports no usage."""
    return max(1, round(len(text) / 4)) if text else 0


def request_cost(
    model: str | None, prompt_tokens: int | None, completion_tokens: int | None
) -> float:
    """TODO (Activity 1): the price of one model call, in US dollars.

    Rules (tests/test_costs.py checks each one):
    - no model (the question was declined or answered from the cache): 0.0
    - a model starting with "ollama/" runs on your own machine: 0.0
    - a model not in PRICES: raise KeyError(f"no price for {model}: add it to PRICES")
    - otherwise: prompt_tokens * input price + completion_tokens * output price, both prices per
      million tokens; None counts as 0 tokens
    - round to 6 decimal places
    """
    if not model or model.startswith("ollama/"):
        return 0.0
    if model not in PRICES:
        raise KeyError(f"no price for {model}: add it to PRICES")
    price = PRICES[model]
    cost = (prompt_tokens or 0) * price["input"] + (completion_tokens or 0) * price["output"]
    return round(cost / 1_000_000, 6)


def measure_stream(pieces, start: float, clock=time.perf_counter) -> dict:
    """TODO (Activity 3): read a streamed answer and time it.

    start is clock() just before the request was sent.
    Rules (tests/test_measure_stream.py checks each one):
    - read every piece; text = all the pieces joined
    - first_token_seconds = clock() - start when the first non-empty piece arrives
      (None if no piece had any text)
    - seconds = clock() - start after the last piece
    - round both to 3 decimal places
    - return {"text": text, "first_token_seconds": ..., "seconds": ...}
    """
    pieces_read = []
    first = None
    for piece in pieces:
        if piece and first is None:
            first = round(clock() - start, 3)
        pieces_read.append(piece or "")
    return {
        "text": "".join(pieces_read),
        "first_token_seconds": first,
        "seconds": round(clock() - start, 3),
    }


def monthly_cost(
    cost_per_1000: float, queries_per_day: int = 10_000, days: int = 30
) -> float:
    """TODO (Homework, Task 1): the model bill for a month, in US dollars.

    Rules (tests/test_monthly_cost.py checks each one):
    - cost_per_1000 is the cost of 1,000 questions, from a load test report
    - monthly cost = cost_per_1000 / 1000 * queries_per_day * days, rounded to 2 decimal places
    - raise ValueError if any argument is negative
    """
    if min(cost_per_1000, queries_per_day, days) < 0:
        raise ValueError("costs, queries and days cannot be negative")
    return round(cost_per_1000 / 1000 * queries_per_day * days, 2)


def summarise_extra(records: list[dict]) -> dict:
    """Day 16 numbers for the dashboard: cache hits, routes and the real cost per 1,000 questions."""
    ok = [r for r in records if r.get("status") == "ok"]
    hits = sum(1 for r in ok if r.get("cached"))
    routes = {}
    for r in ok:
        key = "cache" if r.get("cached") else (r.get("route") or "declined")
        routes[key] = routes.get(key, 0) + 1
    cost = sum(r.get("cost_usd") or 0 for r in ok)
    return {
        "cache_hits": hits,
        "cache_hit_rate": round(hits / len(ok), 3) if ok else 0.0,
        "by_route": routes,
        "cost_usd_logged": round(cost, 6),
        "cost_per_1000": round(cost / len(ok) * 1000, 4) if ok else 0.0,
    }
