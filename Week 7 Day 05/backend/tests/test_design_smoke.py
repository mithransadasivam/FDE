"""Day 2 parts that work from the start: run-cost, ADR and plan checks, the options API."""

from fastapi.testclient import TestClient

from app.design.adr import check_adr
from app.design.cost import estimate, load_prices
from app.design.plan import check_plan
from app.main import app

api = TestClient(app)
RULES = {"engagement_weeks": 6, "validation_weeks": 3, "production_gate_approver": "Helen Achebe",
         "stakeholders": ["Martin Hale", "Deborah Okafor", "Helen Achebe", "Tom Reyes"]}


def test_run_cost_adds_up():
    p = load_prices()
    cost = {"model": "claude-haiku-5.5", "regional": False, "input_tokens_per_page": 1000, "output_tokens_per_page": 0,
            "ocr": False, "fixed_monthly_usd": 0}
    # 1,000 docs x 1 page x 1,000 tokens = 1M input tokens = USD 0.10
    assert estimate(cost, 1000, 1, p)["total_gbp"] == round(0.10 * p["usd to gbp"], 2)


def test_cost_api_has_a_curve():
    data = api.get("/api/design/cost").json()
    ids = {o["id"] for o in data["options"]}
    assert {"A", "C"} <= ids and len(data["curve"]) == 9 and data["value_gbp"] > 0


def test_adr_checks():
    good = ("# ADR-001: Parse then reason\n- **Status:** accepted\n## Context\nUK only, a person decides.\n"
            "## Options considered\nOption A, Option B, Option C. B costs £422 a month.\n## Decision\nB.\n## Consequences\nFine.\n")
    assert all(c["ok"] for c in check_adr(good))
    assert not all(c["ok"] for c in check_adr("# ADR-001: <the decision>\n## Context\n"))


def test_plan_checks():
    plan = {"team": {"fdes": 2, "days_per_week": 5},
            "phases": [{"name": "Proof of concept", "gate": {"week": 2, "approver": "Deborah Okafor"}},
                       {"name": "Pilot", "gate": {"week": 4, "approver": "Deborah Okafor"}},
                       {"name": "Production", "gate": {"week": 6, "approver": "Helen Achebe"}}],
            "tasks": [{"id": "T1", "kind": "build", "owner": "FDE", "start_week": 1, "weeks": 2, "effort_days": 10},
                      {"id": "T2", "kind": "validation", "owner": "MLRO office", "start_week": 3, "weeks": 3, "effort_days": 6}]}
    assert all(c["ok"] for c in check_plan(plan, RULES))
    late = {**plan, "tasks": [{**plan["tasks"][0]}, {**plan["tasks"][1], "start_week": 5}]}
    assert not all(c["ok"] for c in check_plan(late, RULES))
