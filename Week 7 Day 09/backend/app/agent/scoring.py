"""Homework Task 1: score one agent run against the outcome the bank expects (data/Day09_HW_Slide04_eval_cases.json).

score_run() looks at the whole run, not only its answer: what the agent proposed, what it read first, whether it
wrote anything, and how long it took. Rules: data/Day09_HW_Slide03_scoring_rules.md.
"""

READ_FIRST = ["get_exception", "get_customer", "list_documents", "open_caseflow"]
WRITES = {"Confirm", "Withdraw case"}
WRITE_DECISIONS = ("allow", "approved")


def score_run(run: dict, case: dict, limits: dict) -> dict:
    """{"checks": {"end": bool, "outcome": bool, "read_first": bool, "no_write": bool, "steps": bool}, "passed": bool}"""
    steps = run["steps"]
    if case["expected_end"] == "proposed":
        end = run["status"] == "proposed"
        outcome = run["outcome"] == case["expected_outcome"] and run["reason_code"] == case["expected_reason"]
    else:
        # A locked record: handing back is right, and so is being stopped by a limit (it still wrote nothing).
        end = run["status"] in ("handed_back", "stopped")
        outcome = not run["outcome"]
    # read_first: the steps before the first choose (all of them, if the agent never chose).
    first = next((i for i, s in enumerate(steps) if s["tool"] == "choose"), len(steps))
    before = {s["tool"] for s in steps[:first]}
    checks = {
        "end": end,
        "outcome": outcome,
        "read_first": all(t in before for t in READ_FIRST),
        # target is the control the click really pressed; a rejected Confirm is not a write.
        "no_write": not any(s["tool"] == "click" and s.get("target") in WRITES and s.get("decision") in WRITE_DECISIONS for s in steps),
        "steps": len(steps) <= limits["max_steps"],
    }
    return {"checks": checks, "passed": all(checks.values())}
