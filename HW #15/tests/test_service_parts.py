"""Day 15: tests for the finished parts (they pass from the start): the request log, the dashboard
numbers, the health check and the streaming endpoint."""

import json

from fastapi.testclient import TestClient

from app.api import api
from app.monitoring import log_request, percentile, read_requests, summarise
from app.service import PROMPT_VERSION

client = TestClient(api)


def test_the_request_log_keeps_one_line_per_request(tmp_path):
    log = tmp_path / "requests.jsonl"
    log_request(str(log), request_id="a", status="ok", seconds=1.2)
    log_request(str(log), request_id="b", status="error", error="timeout")
    rows = read_requests(str(log))
    assert [r["request_id"] for r in rows] == ["a", "b"] and "time" in rows[0]


def test_the_dashboard_numbers():
    rows = [
        {
            "status": "ok",
            "seconds": s,
            "model": "anthropic/claude-haiku-4.5",
            "tokens": 1000,
        }
        for s in [1, 2, 3, 4, 10]
    ]
    rows += [
        {
            "status": "ok",
            "seconds": 2,
            "model": "openai/gpt-4.1-mini",
            "tokens": 500,
            "fallback": True,
        },
        {"status": "error", "seconds": 20},
    ]
    m = summarise(rows)
    assert (m["requests"], m["errors"], m["error_rate"]) == (7, 1, 0.143)
    assert m["p50_seconds"] == 2 and m["p95_seconds"] == 10 and m["fallbacks"] == 1
    assert m["tokens"] == 5500 and m["cost_usd"] == 0.0155
    assert m["by_model"] == {"anthropic/claude-haiku-4.5": 5, "openai/gpt-4.1-mini": 1}
    assert percentile([], 95) is None


def test_health_and_metrics_answer(fake_chatbot):
    assert client.get("/health").json() == {"status": "ok"}
    m = client.get("/metrics").json()
    assert (
        m["requests"] == 0
        and m["prompt_version"] == PROMPT_VERSION
        and m["alerts"] == []
    )
    assert m["models"] == ["fake-primary", "fake-fallback"]


def test_the_chat_page_and_the_dashboard_are_served():
    assert "Ask the IT policies" in client.get("/").text
    assert "Chatbot dashboard" in client.get("/dashboard").text


def test_the_stream_sends_tokens_then_the_sources(fake_chatbot):
    r = client.post(
        "/ask/stream",
        json={"question": "What is the response target for a P1 incident?"},
    )
    events = [
        json.loads(line[6:])
        for line in r.text.split("\n\n")
        if line.startswith("data: ")
    ]
    assert all(e["type"] == "token" for e in events[:-1]) and len(events) > 3
    assert "15 minutes" in "".join(e["text"] for e in events[:-1])
    assert events[-1]["type"] == "done" and events[-1]["sources"] == [
        "Day06_Slide15_policy_it_support_slas.pdf, page 1"
    ]
    assert (
        json.loads(fake_chatbot.read_text().splitlines()[-1])["request_id"]
        == events[-1]["request_id"]
    )


def test_the_prompt_version_is_a_short_fingerprint():
    assert PROMPT_VERSION.startswith("rag-") and len(PROMPT_VERSION) == 12
