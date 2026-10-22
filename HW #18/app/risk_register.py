"""Day 18: the risk register, kept as data (governance/risk_register.json).

Each risk says what could go wrong, how likely and how bad, which NIST AI RMF function it sits in,
who owns it, which controls reduce it, and where the evidence is that the controls work. A risk
with no owner or no evidence is a wish, not a control.

NIST AI RMF functions: GOVERN (culture, roles, policies), MAP (context and risks identified),
MEASURE (risks analysed and tracked with tests and metrics), MANAGE (risks treated and monitored).

Done: rating(), FUNCTIONS, STATUSES.
Activity 4: fill in check_register(). Check it with tests/test_risk_register.py.
Homework, Task 1: fill in overdue(). Check it with tests/test_overdue.py.
"""

from datetime import date
from pathlib import Path

FUNCTIONS = ["GOVERN", "MAP", "MEASURE", "MANAGE"]
STATUSES = ["open", "mitigated", "accepted"]


def rating(likelihood: int, impact: int) -> dict:
    """Likelihood and impact from 1 to 5. Score = likelihood x impact: 15 or more is high, 8 or
    more is medium, otherwise low."""
    score = likelihood * impact
    return {
        "score": score,
        "level": "high" if score >= 15 else "medium" if score >= 8 else "low",
    }


def check_register(risks: list[dict], root: str = ".") -> list[str]:
    """Everything wrong with the register. An empty list means it passes.

    Rules (tests/test_risk_register.py checks each one). For each risk, in order, with
    rid = risk.get("id", "?"), collect:
    - "duplicate id: {rid}"                      if the id was already seen
    - f"{rid}: function must be one of GOVERN, MAP, MEASURE, MANAGE"   if risk.get("function") not in FUNCTIONS
    - f"{rid}: likelihood and impact must be whole numbers from 1 to 5"
                                                 if either is not an int in range 1..5
    - f"{rid}: needs an owner"                   if not risk.get("owner")
    - f"{rid}: needs at least one control"       if not risk.get("controls")
    - f"{rid}: status must be one of open, mitigated, accepted"        if risk.get("status") not in STATUSES
    - f"{rid}: needs evidence"                   if not risk.get("evidence")
    - f"{rid}: no evidence at {path}"            for each path in risk.get("evidence") or []
                                                 where Path(root, path) does not exist
    - f"{rid}: an accepted risk needs accepted_by and a reason"
                                                 if status is "accepted" and either is missing
    """
    problems: list[str] = []
    seen: set = set()
    for risk in risks:
        rid = risk.get("id", "?")
        if rid in seen:
            problems.append(f"duplicate id: {rid}")
        seen.add(rid)
        if risk.get("function") not in FUNCTIONS:
            problems.append(f"{rid}: function must be one of GOVERN, MAP, MEASURE, MANAGE")
        for key in ("likelihood", "impact"):
            v = risk.get(key)
            if not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= 5:
                problems.append(f"{rid}: likelihood and impact must be whole numbers from 1 to 5")
                break
        if not risk.get("owner"):
            problems.append(f"{rid}: needs an owner")
        if not risk.get("controls"):
            problems.append(f"{rid}: needs at least one control")
        if risk.get("status") not in STATUSES:
            problems.append(f"{rid}: status must be one of open, mitigated, accepted")
        if not risk.get("evidence"):
            problems.append(f"{rid}: needs evidence")
        for path in risk.get("evidence") or []:
            if not Path(root, path).exists():
                problems.append(f"{rid}: no evidence at {path}")
        if risk.get("status") == "accepted" and not (
            risk.get("accepted_by") and risk.get("reason")
        ):
            problems.append(f"{rid}: an accepted risk needs accepted_by and a reason")
    return problems


def overdue(risks: list[dict], today: date | None = None) -> list[str]:
    """The ids of risks whose review is overdue, so monitoring can chase them.

    Rules (tests/test_overdue.py checks each one):
    - today defaults to date.today()
    - a "mitigated" risk is never overdue here
    - any other risk is overdue if its "review_by" date ("YYYY-MM-DD", use date.fromisoformat) is
      before today, or if it has no "review_by" at all: nobody has planned to look at it again
    - return the ids in register order
    """
    today = today or date.today()
    return [
        r["id"]
        for r in risks
        if r.get("status") != "mitigated"
        and (not r.get("review_by") or date.fromisoformat(r["review_by"]) < today)
    ]
