"""Ticket ENG-202: check candidate architectures against the client's rules. 8 tests."""

import json

from fastapi.testclient import TestClient

from app.config import ARCHITECTURE_DIR
from app.design.architecture import Architecture, check_architecture
from app.main import app


def load(name):
    return Architecture(**json.loads((ARCHITECTURE_DIR / name).read_text(encoding="utf-8")))


def tiny(nodes, edges):
    base = [{"id": "p", "label": "Person", "kind": "person", "lane": "client", "row": 0},
            {"id": "d", "label": "Decision", "kind": "decision", "lane": "bank", "row": 1},
            {"id": "log", "label": "Log", "kind": "audit_log", "lane": "aws", "row": 2}]
    return Architecture(id="T", name="t", summary="", time_to_pilot_weeks=1, cost={},
                        nodes=base + nodes, edges=[{"from": "p", "to": "d"}] + edges)


def rules(arch):
    return [v.rule for v in check_architecture(arch)]


def test_option_a_meets_every_rule():
    assert check_architecture(load("option_a.json")) == []


def test_option_c_breaks_six_times_in_rule_order():
    vs = check_architecture(load("option_c.json"))
    assert [v.rule for v in vs] == ["residency", "public_ai", "read_only", "human_decides", "human_decides", "audit"]
    assert vs[0].message == "Customer data leaves the UK at Public document AI (US)" and vs[0].node == "saas"
    assert vs[2].edge == ["saas", "caseflow"]
    assert vs[4].message == "No person makes the decision" and vs[4].node is None and vs[4].edge is None


def test_residency_only_for_customer_data():
    a = tiny([{"id": "x", "label": "Cache", "kind": "store", "lane": "external", "row": 3, "region": "eu"}], [])
    assert rules(a) == []
    a.nodes[-1].customer_data = True
    assert rules(a) == ["residency"]


def test_public_models_are_blocked():
    m = {"id": "m", "label": "M", "kind": "model", "lane": "external", "row": 3, "hosting": "public"}
    assert rules(tiny([m], [{"from": "m", "to": "log"}])) == ["public_ai"]


def test_people_may_write_to_read_only_systems_but_services_may_not():
    sysnode = {"id": "cf", "label": "CF", "kind": "system", "lane": "bank", "row": 3, "read_only": True}
    svc = {"id": "s", "label": "Svc", "kind": "service", "lane": "aws", "row": 4}
    assert rules(tiny([sysnode, svc], [{"from": "p", "to": "cf"}])) == []
    assert rules(tiny([sysnode, svc], [{"from": "s", "to": "cf"}])) == ["read_only"]


def test_a_model_must_not_decide():
    m = {"id": "m", "label": "M", "kind": "model", "lane": "aws", "row": 3, "hosting": "bedrock"}
    vs = check_architecture(tiny([m], [{"from": "m", "to": "d"}, {"from": "m", "to": "log"}]))
    assert [(v.rule, v.message) for v in vs] == [("human_decides", "M makes the decision")]


def test_every_model_is_logged():
    m = {"id": "m", "label": "M", "kind": "model", "lane": "aws", "row": 3, "hosting": "bedrock"}
    assert rules(tiny([m], [])) == ["audit"]


def test_api_returns_violations_per_option():
    data = TestClient(app).get("/api/design/options").json()
    by = {o["id"]: o for o in data["options"]}
    assert by["A"]["violations"] == [] and len(by["C"]["violations"]) == 6
    assert len(data["rules"]) == 5
