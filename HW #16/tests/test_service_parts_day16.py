"""Day 16: tests for the finished parts (they pass from the start): routes and costs in the log,
the dashboard numbers, clearing the cache, and the load test report."""

from fastapi.testclient import TestClient

from app.api import api
from app.perf import estimate_tokens, summarise_extra
from scripts.load_test import draw, report

client = TestClient(api)


def test_the_extra_dashboard_numbers():
    rows = [
        {"status": "ok", "route": "large", "cost_usd": 0.004},
        {"status": "ok", "route": "small", "cost_usd": 0.0},
        {"status": "ok", "cached": True, "route": "large", "cost_usd": 0.0},
        {"status": "ok", "route": None, "cost_usd": 0.0},
        {"status": "error"},
    ]
    m = summarise_extra(rows)
    assert m["cache_hits"] == 1 and m["cache_hit_rate"] == 0.25
    assert m["by_route"] == {"large": 1, "small": 1, "cache": 1, "declined": 1}
    assert m["cost_per_1000"] == 1.0


def test_every_answer_is_logged_with_route_and_cost(fake_chatbot):
    import json

    client.post(
        "/ask", json={"question": "What is the response target for a P1 incident?"}
    )
    entry = json.loads(fake_chatbot.read_text().splitlines()[-1])
    assert (
        entry["route"] == "large"
        and entry["cost_usd"] == 0.0
        and entry["cached"] is False
    )
    assert entry["prompt_tokens"] == 600 and entry["completion_tokens"] > 0


def test_metrics_show_the_settings(fake_chatbot):
    m = client.get("/metrics").json()
    assert m["settings"] == {
        "cache": False,
        "routing": False,
        "small_model": "fake-small",
    }
    assert "cache_hit_rate" in m and "by_route" in m


def test_the_cache_can_be_cleared(fake_chatbot, fresh_cache):
    fresh_cache.put("k", {"answer": "x"})
    assert client.post("/cache/clear").json() == {"removed": 1}


def test_the_load_test_draws_the_same_questions_every_time():
    a, b = (
        draw("data/Day16_Slide09_load_questions.csv", 30),
        draw("data/Day16_Slide09_load_questions.csv", 30),
    )
    assert a == b and len(set(a)) < 30  # popular questions come up more than once


def test_the_load_test_report():
    results = [
        {
            "status": "ok",
            "seconds": s,
            "cost_usd": 0.002,
            "cached": False,
            "route": "large",
            "tokens": 1000,
        }
        for s in [1, 2, 3, 4]
    ] + [{"status": "error", "seconds": 30}]
    r = report(results, wall=10.0, label="x", users=2)
    assert (r["requests"], r["errors"], r["p50_seconds"], r["p95_seconds"]) == (
        5,
        1,
        2,
        4,
    )
    assert (
        r["throughput_per_second"] == 0.5
        and r["cost_per_1000"] == 2.0
        and r["routes"] == {"large": 4}
    )
    assert estimate_tokens("x" * 400) == 100
