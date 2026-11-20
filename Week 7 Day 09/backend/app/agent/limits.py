"""Ticket ENG-902: stop a run before it goes on too long, costs too much, or goes round in circles.

check_limits() is called before every action the agent wants to take. It returns None if the action may go ahead,
or the reason the run must stop, word for word as the ticket lists it.
"""


def describe(action: dict) -> str:
    """How an action reads in a stop reason: click "Save", type in "Note", get_customer CU-022578 (done)."""
    tool, args = action.get("tool", ""), action.get("args", {}) or {}
    if tool == "click":
        return f'click "{args.get("name", "")}"'
    if tool == "type":
        return f'type in "{args.get("field", "")}"'
    if tool == "choose":
        return f'choose "{args.get("option", "")}" in "{args.get("field", "")}"'
    first = next(iter(args.values()), "")
    return f"{tool} {first}".strip()


def check_limits(steps: list[dict], next_action: dict, limits: dict, started_at: float, now: float) -> str | None:
    """The reason this run must stop before `next_action`, or None.

    steps        the steps taken so far, oldest first: each has "tool", "args", "tokens_in" and "tokens_out"
    next_action  the action the agent wants to take now: "tool" and "args"
    limits       max_steps, max_tokens, max_seconds and max_repeats (data/Day09_Slide15_run_limits.json)

    Check in this order, and return the first that applies:
      1. len(steps) >= max_steps                       -> "Step limit: 25 steps"
      2. tokens in + out of every step >= max_tokens   -> "Token budget: 150,000 tokens used"
      3. now - started_at >= max_seconds               -> "Time limit: 300 s"
      4. the last max_repeats - 1 steps are each the same tool with the same args as next_action
                                                       -> 'Repeating: click "Save" 3 times in a row'
    Numbers are the limits' own, written with a thousands comma (150,000). Use describe() for the action.
    """
    if len(steps) >= limits["max_steps"]:
        return f"Step limit: {limits['max_steps']:,} steps"
    if sum(s.get("tokens_in", 0) + s.get("tokens_out", 0) for s in steps) >= limits["max_tokens"]:
        return f"Token budget: {limits['max_tokens']:,} tokens used"
    if now - started_at >= limits["max_seconds"]:
        return f"Time limit: {limits['max_seconds']:,} s"
    n = limits["max_repeats"] - 1
    recent = steps[-n:] if n > 0 else []
    same = lambda a: a.get("tool") == next_action.get("tool") and (a.get("args") or {}) == (next_action.get("args") or {})
    if len(recent) == n and all(same(s) for s in recent):
        return f"Repeating: {describe(next_action)} {limits['max_repeats']} times in a row"
    return None
