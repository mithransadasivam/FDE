"""Homework Task 1: score one case of the crash test from the bank's own records (data/Day10_HW_Slide03_exactly_once_rules.md).

result: what the case left behind (crashtest.result_of): "end", "counts" (requests, reminders, caseflow_outcomes,
outcome_comments, escalations), "agent_runs" (finished agent runs per round, e.g. {"1": 1, "2": 1}) and "crashes" (the points that fired).
case: the case in data/Day10_HW_Slide04_crash_plan.json: "expected_end" and "expected" (the same counts).
"""


def score_case(result: dict, case: dict) -> dict:
    """{"checks": {"end": bool, "messages": bool, "caseflow": bool, "escalation": bool, "agent_once": bool}, "passed": bool}"""
    got, want = result["counts"], case["expected"]
    checks = {
        "end": result["end"] == case["expected_end"],
        # exactly, never "at least": a check that passes on "one or more" cannot catch a write that happened twice
        "messages": got["requests"] == want["requests"] and got["reminders"] == want["reminders"],
        "caseflow": got["caseflow_outcomes"] == want["caseflow_outcomes"] and got["outcome_comments"] == want["outcome_comments"],
        "escalation": got["escalations"] == want["escalations"],
        # finished runs only: a crash can cut a run short (that costs tokens), but a round never finishes twice
        "agent_once": all(n <= 1 for n in result["agent_runs"].values()),
    }
    return {"checks": checks, "passed": all(checks.values())}
