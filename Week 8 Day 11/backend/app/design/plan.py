"""Checks a delivery plan against the client's rules and the team's capacity (done, not a ticket)."""

PHASES = ["Proof of concept", "Pilot", "Production"]


def check_plan(plan: dict, rules: dict) -> list[dict]:
    weeks = rules["engagement_weeks"]
    phases = plan.get("phases", [])
    tasks = plan.get("tasks", [])
    team = plan.get("team", {})
    names = [p.get("name") for p in phases]
    out = [{"check": "Three phases, in order: proof of concept, pilot, production", "ok": names == PHASES}]
    gates_ok = all(p.get("gate", {}).get("approver") in rules["stakeholders"] for p in phases) and len(phases) == 3
    out.append({"check": "Every gate has a named client approver", "ok": gates_ok})
    prod = next((p for p in phases if p.get("name") == "Production"), {})
    out.append({"check": f"Production gate approved by {rules['production_gate_approver']}",
                "ok": prod.get("gate", {}).get("approver") == rules["production_gate_approver"]})
    val = [t for t in tasks if t.get("kind") == "validation"]
    long_enough = any(t.get("weeks", 0) >= rules["validation_weeks"] for t in val)
    out.append({"check": f"Model validation runs at least {rules['validation_weeks']} weeks", "ok": long_enough})
    gate_week = prod.get("gate", {}).get("week", weeks)
    ends_in_time = any(t.get("start_week", 0) + t.get("weeks", 0) - 1 <= gate_week for t in val) and bool(val)
    out.append({"check": "Validation finishes by the production gate", "ok": ends_in_time and long_enough})
    last = max((t.get("start_week", 1) + t.get("weeks", 1) - 1 for t in tasks), default=0)
    out.append({"check": f"Everything ends by week {weeks}", "ok": bool(tasks) and last <= weeks})
    capacity = team.get("fdes", 0) * team.get("days_per_week", 0) * weeks
    used = sum(t.get("effort_days", 0) for t in tasks if t.get("owner") == "FDE")
    out.append({"check": f"FDE effort within capacity ({used:g} of {capacity:g} days)", "ok": bool(tasks) and used <= capacity})
    return out
