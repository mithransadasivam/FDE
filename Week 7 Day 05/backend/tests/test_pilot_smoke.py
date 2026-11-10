"""Day 5 smoke tests: they pass before the tickets are done."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.platform.guardrail import list_policies, load_policy, scripted_guardrail, summary
from app.platform.residency import residency, routing

client = TestClient(app)
FIX = Path(__file__).parent / "fixtures"


def test_routing_from_the_model_id():
    assert routing("anthropic.claude-sonnet-5") == "in-region"
    assert routing("eu.anthropic.claude-haiku-5-5") == "geo"
    assert routing("global.anthropic.claude-sonnet-5") == "global"


def test_residency_of_the_adr001_model_and_the_fix():
    assert not residency("eu.anthropic.claude-haiku-5-5", "eu-west-2")["stays_in_uk"]
    assert not residency("anthropic.claude-haiku-5-5", "eu-west-2")["stays_in_uk"]  # London does not serve it in-Region
    assert residency("anthropic.claude-sonnet-5", "eu-west-2")["stays_in_uk"]


def test_status_endpoint():
    r = client.get("/api/pilot/status").json()
    assert r["settings"]["region"] == "eu-west-2" and len(r["models"]) == 4


def test_policies_load_and_summarise():
    assert "uc1_v1" in list_policies()
    s = summary(load_policy("uc1_v1"))
    assert "NAME" in s["masked"] and not s["prompt_attack"]


def test_scripted_guardrail_v1_masks_the_name():
    reply = (FIX / "extract_v2" / "P-003.json").read_text()
    out = json.loads(scripted_guardrail(load_policy("uc1_v1"), "OCR words", reply))
    assert next(f for f in out["fields"] if f["name"] == "full_name")["value"] == "{NAME}"


def test_plan_endpoint_without_a_plan():
    assert client.get("/api/pilot/plan").status_code == 404  # conftest points FDE_PLAN_FILE at an empty folder


def test_probes_run_with_v1():
    r = client.post("/api/pilot/guardrails/uc1_v1/probes").json()
    assert r["attacks"] == 2 and len(r["results"]) == 3


def test_pilot_password_middleware():
    from fastapi import FastAPI

    from app.platform.security import PilotPassword

    mini = FastAPI()

    @mini.get("/x")
    def x():
        return {"ok": True}

    mini.add_middleware(PilotPassword, secret_arn="arn:test", fetch=lambda arn: "s3cret")
    c = TestClient(mini)
    assert c.get("/x").status_code == 401
    assert c.get("/x", auth=("analyst", "wrong")).status_code == 401
    assert c.get("/x", auth=("analyst", "s3cret")).json() == {"ok": True}
