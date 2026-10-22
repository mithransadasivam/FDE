"""Day 15, Activity 4: call_with_fallback() retries, waits longer each time, then uses the fallback."""

import pytest
from fastapi.testclient import TestClient

from app.api import api
from app.reliability import ModelUnavailable, call_with_fallback


def scripted(*outcomes):
    """A fake model call: each outcome is an error to raise or a value to return, in order."""
    calls = []

    def call(model):
        calls.append(model)
        outcome = outcomes[len(calls) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return call, calls


def test_the_first_try_works():
    call, calls = scripted("hello")
    waits = []
    r = call_with_fallback(
        call, ["primary", "fallback"], retries=2, backoff=0.5, sleep=waits.append
    )
    assert r == {
        "result": "hello",
        "model": "primary",
        "fallback": False,
        "attempts": 1,
    }
    assert calls == ["primary"] and waits == []


def test_a_retry_after_a_short_wait():
    call, calls = scripted(TimeoutError(), "hello")
    waits = []
    r = call_with_fallback(
        call, ["primary", "fallback"], retries=2, backoff=0.5, sleep=waits.append
    )
    assert r["model"] == "primary" and r["attempts"] == 2 and waits == [0.5]
    assert calls == ["primary", "primary"]


def test_the_fallback_after_every_retry_fails():
    call, calls = scripted(
        ConnectionError(), TimeoutError(), ConnectionError(), "from the fallback"
    )
    waits = []
    r = call_with_fallback(
        call, ["primary", "fallback"], retries=2, backoff=0.5, sleep=waits.append
    )
    assert r == {
        "result": "from the fallback",
        "model": "fallback",
        "fallback": True,
        "attempts": 4,
    }
    assert calls == ["primary"] * 3 + ["fallback"] and waits == [0.5, 1.0]


def test_an_error_that_will_not_go_away_is_raised_at_once():
    call, calls = scripted(ValueError("bad request"), "never used")
    with pytest.raises(ValueError):
        call_with_fallback(
            call, ["primary", "fallback"], retries=2, sleep=lambda s: None
        )
    assert calls == ["primary"]


def test_every_model_failing_raises_model_unavailable_listing_the_errors():
    call, calls = scripted(*[TimeoutError()] * 4)
    with pytest.raises(ModelUnavailable) as e:
        call_with_fallback(
            call, ["primary", "fallback"], retries=1, backoff=0.5, sleep=lambda s: None
        )
    assert len(calls) == 4
    assert str(e.value) == (
        "primary: TimeoutError; primary: TimeoutError; "
        "fallback: TimeoutError; fallback: TimeoutError"
    )


def test_no_retries_means_straight_to_the_fallback():
    call, calls = scripted(TimeoutError(), "ok")
    waits = []
    r = call_with_fallback(call, ["primary", "fallback"], retries=0, sleep=waits.append)
    assert r["model"] == "fallback" and calls == ["primary", "fallback"] and waits == []


def test_a_simulated_outage_is_answered_by_the_fallback(fake_chatbot, monkeypatch):
    monkeypatch.setenv("SIMULATE_OUTAGE", "primary")
    body = (
        TestClient(api)
        .post("/ask", json={"question": "How often are laptops replaced?"})
        .json()
    )
    assert (
        body["model"] == "fake-fallback"
        and body["fallback"] is True
        and "4 years" in body["answer"]
    )


def test_a_simulated_outage_of_every_model_gives_503(fake_chatbot, monkeypatch):
    monkeypatch.setenv("SIMULATE_OUTAGE", "all")
    r = TestClient(api).post(
        "/ask", json={"question": "How often are laptops replaced?"}
    )
    assert r.status_code == 503
