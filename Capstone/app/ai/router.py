"""Model router (Day 3, Prompts C): which model runs which kind of step, with prices for the cost report.

small  = extraction and point-ticking (cheap, high volume)
large  = judgement: scoring, suggestions, drafting
local  = any step that sees identity (it never leaves the machine)
In fake mode no model runs, but the same choice is made and the cost is recorded as if it had (flagged simulated).
"""
from app.config import get_settings

# US dollars per 1,000,000 tokens (input, output). Illustrative list prices; edit them to match your provider.
PRICES = {
    "large": (1.00, 5.00),
    "small": (0.10, 0.40),
    "local": (0.0, 0.0),
    "fallback": (0.15, 0.60),
}
TASK_TIER = {"extraction": "small", "point_ticking": "small", "classification": "small",
             "judgement": "large", "scoring": "large", "suggestion": "large", "drafting": "large", "chat": "large",
             "identity": "local"}


def tier_for(task: str) -> str:
    if not get_settings().router_enabled:
        return "large"  # the "before routing" state used by the performance report
    return TASK_TIER.get(task, "large")


def model_for(tier: str) -> str:
    s = get_settings()
    return {"large": s.large_model, "small": s.small_model, "local": s.local_model, "fallback": s.fallback_model}[tier]


def pick(task: str) -> tuple[str, str]:
    """(tier, model name) for a task."""
    tier = tier_for(task)
    return tier, model_for(tier)


def cost_usd(tier: str, tokens_in: int, tokens_out: int) -> float:
    pin, pout = PRICES[tier]
    return round((tokens_in * pin + tokens_out * pout) / 1_000_000, 6)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
