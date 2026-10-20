"""Day 12: review an agent's trace and list what went wrong.

Activity 4: fill in trace_problems(). Check it with tests/test_trace_review.py.
"""

import json  # noqa: F401  (you will need it)


def trace_problems(run: dict) -> list[str]:
    """TODO (Activity 4): read a run from run_agent() and list its problems, in this order.

    Rules (tests/test_trace_review.py checks each one):
    - run["stopped"] == "step_limit":  "hit the step limit without an answer"
    - run["stopped"] == "repeated":    "repeated the same tool call"
    - for every action whose result is JSON with an "error" key, in step order:
                                       "step N: <tool name> returned an error"
    - no actions in any step:          "answered without using any tool"
    - for every read_article result whose "published" date is before "2024-01-01", if that article's
      id appears in the answer:        "relied on an old article (KB-0412, published 2019-06-11)"
    - the answer contains no line starting "Sources:" (only when run["stopped"] == "answer"):
                                       "the answer lists no sources"
    - return [] when there is no problem
    """
    problems = []
    if run["stopped"] == "step_limit":
        problems.append("hit the step limit without an answer")
    if run["stopped"] == "repeated":
        problems.append("repeated the same tool call")
    actions = [(s["step"], a) for s in run["trace"] for a in s["actions"]]
    articles = []
    for step, a in actions:
        try:
            result = json.loads(a["result"])
        except (TypeError, ValueError):
            continue
        if not isinstance(result, dict):
            continue
        if "error" in result:
            problems.append(f"step {step}: {a['name']} returned an error")
        elif a["name"] == "read_article":
            articles.append(result)
    if not actions:
        problems.append("answered without using any tool")
    for art in articles:
        if art.get("published", "9999") < "2024-01-01" and art.get("id", "?") in run["answer"]:
            problems.append(
                f"relied on an old article ({art['id']}, published {art['published']})"
            )
    if run["stopped"] == "answer" and not any(
        line.strip().startswith("Sources:") for line in run["answer"].splitlines()
    ):
        problems.append("the answer lists no sources")
    return problems
