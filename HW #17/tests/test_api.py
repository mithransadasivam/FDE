"""Day 15, Activity 1: POST /ask answers one question as JSON. Uses the fake chatbot: no models."""

import json

from fastapi.testclient import TestClient

from app import service
from app.api import UNAVAILABLE, api
from app.reliability import ModelUnavailable

client = TestClient(api)


def test_a_known_question_gets_an_answer_with_sources(fake_chatbot):
    r = client.post(
        "/ask", json={"question": "How long can a VPN session stay connected?"}
    )
    assert r.status_code == 200
    body = r.json()
    assert "12 hours" in body["answer"] and body["declined"] is False
    assert body["sources"] == ["Day06_Slide15_policy_vpn_remote_access.pdf, page 1"]
    assert body["model"] == "fake-primary" and body["fallback"] is False
    assert len(body["request_id"]) == 12 and body["seconds"] >= 0


def test_an_unknown_question_is_declined_without_a_model(fake_chatbot):
    body = client.post(
        "/ask", json={"question": "What is on the cafeteria menu?"}
    ).json()
    assert body["declined"] is True and body["sources"] == [] and body["model"] is None


def test_an_empty_or_huge_question_is_refused_before_ask_runs(fake_chatbot):
    assert client.post("/ask", json={"question": ""}).status_code == 422
    assert client.post("/ask", json={"question": "x" * 4001}).status_code == 422
    assert client.post("/ask", json={}).status_code == 422


def test_every_answer_is_logged_with_its_request_id(fake_chatbot):
    body = client.post(
        "/ask", json={"question": "How often are laptops replaced?"}
    ).json()
    entry = json.loads(fake_chatbot.read_text(encoding="utf-8").splitlines()[-1])
    assert entry["request_id"] == body["request_id"] and entry["status"] == "ok"
    assert entry["model"] == "fake-primary" and entry["fallback"] is False
    assert (
        entry["tokens"] > 0
        and entry["declined"] is False
        and entry["seconds"] == body["seconds"]
    )


def test_no_model_available_gives_503_and_logs_the_error(fake_chatbot, monkeypatch):
    def down(question):
        raise ModelUnavailable(
            "fake-primary: TimeoutError; fake-fallback: TimeoutError"
        )

    monkeypatch.setattr(service, "answer", down)
    r = client.post(
        "/ask", json={"question": "How long can a VPN session stay connected?"}
    )
    assert r.status_code == 503 and r.json()["detail"] == UNAVAILABLE
    entry = json.loads(fake_chatbot.read_text(encoding="utf-8").splitlines()[-1])
    assert entry["status"] == "error" and "TimeoutError" in entry["error"]
