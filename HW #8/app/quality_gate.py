"""Day 8: a quality gate. Compare measured numbers with agreed thresholds and list what fails.

load_thresholds() is done.
Activity 3: fill in quality_gate(). Check it with tests/test_quality_gate.py.
"""

import json


def load_thresholds(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def quality_gate(summary: dict, thresholds: dict) -> list[str]:
    """TODO (Activity 3): list every threshold the summary does not meet.

    thresholds looks like {"min_hit_rate": 0.9, "max_avg_seconds": 5}.
    Rules (tests/test_quality_gate.py checks each one):
    - a key starting "min_" means summary[<rest of the key>] must be >= the value
    - a key starting "max_" means summary[<rest of the key>] must be <= the value
    - for a metric that fails, the problem is f"{metric} is {actual}, needs >= {value}"
      (or "<=" for max_)
    - for a metric missing from the summary, the problem is f"{metric} is missing"
    - a key that starts with neither raises ValueError
    - return the problems in the same order as the thresholds; [] means the gate passes
    """
    problems = []
    for key, value in thresholds.items():
        if key.startswith("min_"):
            metric, op = key[4:], ">="
        elif key.startswith("max_"):
            metric, op = key[4:], "<="
        else:
            raise ValueError(f"threshold {key!r} must start with min_ or max_")
        if metric not in summary:
            problems.append(f"{metric} is missing")
            continue
        actual = summary[metric]
        if (actual < value) if op == ">=" else (actual > value):
            problems.append(f"{metric} is {actual}, needs {op} {value}")
    return problems
