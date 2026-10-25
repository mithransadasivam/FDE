"""Phase 3: the service. Health, ready, metrics, a request id on everything, and secrets nowhere in the logs."""
import json

import pytest
from fastapi.testclient import TestClient

from tower.api import create_app


@pytest.fixture
def client(tower):
    return TestClient(create_app(tower))


def test_health_and_request_id(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok" and len(r.headers["x-request-id"]) >= 8
    assert client.get("/health", headers={"x-request-id": "abc123"}).headers["x-request-id"] == "abc123"


def test_ready_turns_false_when_the_model_connection_stops_and_true_again(client):
    assert client.get("/ready").status_code == 200
    client.post("/admin/model", params={"down": True})
    r = client.get("/ready")
    assert r.status_code == 503 and r.json()["checks"]["model"] is False and r.json()["checks"]["database"] is True
    client.post("/admin/model", params={"down": False})
    assert client.get("/ready").status_code == 200


def test_admin_endpoints_do_not_exist_unless_enabled(tower):
    tower.s = tower.s.with_(admin_debug=False)
    c = TestClient(create_app(tower))
    assert c.post("/admin/model", params={"down": True}).status_code == 404


def test_triage_and_incidents(client):
    r = client.post("/triage", json={})
    assert r.status_code == 200 and r.json()["count"] == 10 and r.json()["alerts"] == 22
    inc = client.get("/incidents").json()
    assert len(inc) == 10 and inc[0]["incident_id"] == "INC-3001"
    one = client.get("/incidents/INC-3008").json()
    assert "Winter2026" not in json.dumps(one) and "900318" not in json.dumps(one)
    assert client.get("/incidents/INC-9999").status_code == 404
    assert client.get("/scenarios/score").json()["summary"]["grouping"] == 10


def test_triage_accepts_new_alerts_and_validates_them(client):
    client.post("/triage", json={})
    ok = client.post("/triage", json={"alerts": [{"alert_id": "AL-950", "time": "2026-10-24 13:20", "source": "monitor", "service": "fs-02",
                                                  "check": "disk_space", "severity": "warning", "status": "firing", "message": "Disk 92%"}]})
    assert ok.status_code == 200 and ok.json()["count"] == 11
    bad = client.post("/triage", json={"alerts": [{"alert_id": "x", "time": "now", "severity": "huge"}]})
    assert bad.status_code == 422


def test_ask_and_sources(client):
    client.post("/triage", json={})
    r = client.post("/ask", json={"question": "What does runbook RB-04 say to do first?"}).json()
    assert r["route"] == "small" and r["sources"] and r["answer"]
    assert client.post("/ask", json={"question": ""}).status_code == 422
    assert client.post("/ask", json={"question": "x" * 6000}).status_code == 422


def test_ask_stream_is_ndjson(client):
    client.post("/triage", json={})
    r = client.post("/ask/stream", json={"question": "What does runbook RB-04 say to do first?"})
    events = [json.loads(line) for line in r.text.splitlines() if line]
    assert events[0]["type"] == "meta" and events[-1]["type"] == "done"


def test_approval_flow_over_http(client):
    client.post("/triage", json={})
    inc = client.get("/incidents/INC-3007").json()
    rid = inc["request_id"]
    r = client.post(f"/actions/{rid}/decide", json={"approver": "L. Brandt", "reason": ""})
    assert r.status_code == 422  # freeze: reason needed
    client.post(f"/actions/{rid}/decide", json={"approver": "L. Brandt", "reason": "node 2 leaking, restart one node"})
    assert client.get("/actions-log").json()["lines"] == []
    r = client.post(f"/actions/{rid}/decide", json={"approver": "K. Adeyemi", "reason": "freeze, tier 1, owner approved"})
    assert r.json()["status"] == "CHANGE_DONE" and len(client.get("/actions-log").json()["lines"]) == 1
    assert client.post(f"/actions/{rid}/decide", json={"approver": "K. Adeyemi", "reason": "again please"}).json()["executed_now"] is False
    assert len(client.get("/actions-log").json()["lines"]) == 1


def test_two_services_in_one_request_is_rejected_at_the_door(client):
    client.post("/triage", json={})
    r = client.post("/actions", json={"incident_id": "INC-3007", "runbook_id": "RB-02", "step_no": 3, "action": "restart_service",
                                      "target_service": "payportal,hr-selfservice", "reason": "restart both"})
    assert r.status_code == 422


def test_metrics_count_requests_errors_model_calls_tokens_and_percentiles(client):
    client.post("/triage", json={})
    client.post("/ask", json={"question": "Why are the Payment Portal and HR Self-Service down at the same time?"})
    client.get("/incidents/NOPE")
    m = client.get("/metrics").json()
    assert m["requests_total"] >= 3 and m["model_calls_total"] > 0 and m["tokens_total"] > 0
    assert m["latency_ms"]["p95"] >= m["latency_ms"]["p50"] > 0
    assert m["model_calls"]["planner"] == 8 and m["settings"]["guardrails"] is True
    assert "tower_requests_total" in client.get("/metrics", params={"format": "prometheus"}).text


def test_traces_exist_for_a_request(client):
    r = client.post("/ask", json={"question": "What does runbook RB-04 say to do first?"})
    rid = r.headers["x-request-id"]
    names = {s["name"] for s in client.get("/traces/recent", params={"request_id": rid}).json()}
    assert {"http", "ask", "retrieve"} <= names and any(n.startswith("llm.") for n in names)


def test_no_secret_in_any_log_line_or_response(client, tower):
    client.post("/triage", json={})
    client.post("/ask", json={"question": "Why are the Payment Portal and HR Self-Service down at the same time?"})
    log = tower.s.app_log.read_text(encoding="utf-8")
    assert log.strip()
    for needle in ("Winter2026!", "tok_test_8f2a91c7", "900318"):
        assert needle not in log


def test_status_page_has_plain_words_and_no_technical_detail(client):
    client.post("/triage", json={})
    page = client.get("/status-page").json()
    assert page["items"] and not page["all_clear"]
    blob = json.dumps(page)
    for tech in ("db-core", "5432", "RB-", "failover", "restart", "INC-", "203.0.113"):
        assert tech not in blob
    assert "Core Database" in blob or "Payment Portal" in blob


def test_replay_grows_an_incident_as_the_cascade_arrives(client):
    client.post("/replay/reset")
    steps = [client.post("/replay/step").json() for _ in range(9)]
    s03 = [s for s in steps if s.get("incident_id") == "INC-3003"]
    assert [s["incident_alerts"] for s in s03] == [1, 2, 3, 4, 5]
    assert s03[0]["new_incident"] and all(s["grew"] for s in s03[1:])


def test_escalation_pages_the_duty_manager_after_15_minutes(client):
    client.post("/triage", json={})
    assert client.post("/escalations/run").json()["paged"] == []
    client.post("/admin/clock", params={"minutes": 20})
    paged = client.post("/escalations/run").json()["paged"]
    assert paged and paged[0]["paged"] == "K. Adeyemi"
    assert client.post("/escalations/run").json()["paged"] == []  # once only
    audit = client.get("/audit").json()
    assert any(a["event"] == "escalated" for a in audit)
    assert "900312" not in json.dumps(audit)


def test_crew_stream_emits_each_agent_step_then_the_incident(client):
    client.post("/triage", json={})
    r = client.post("/incidents/INC-3003/crew/stream")
    events = [json.loads(line) for line in r.text.splitlines() if line]
    steps = [e["step"]["agent"] for e in events if e["type"] == "step"]
    assert steps[0] == "Dispatcher" and "Planner" in steps and "Gatekeeper" in steps and events[-1]["type"] == "done"
