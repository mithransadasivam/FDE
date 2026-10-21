"""Day 16, Activity 1: request_cost() prices one model call from its tokens."""

from types import SimpleNamespace

import pytest

from app import service
from app.perf import PRICES, request_cost
from app.rag import MODEL


def test_input_and_output_tokens_have_different_prices():
    # 2,000 prompt tokens at 1.00 per million + 300 answer tokens at 5.00 per million
    assert request_cost("anthropic/claude-haiku-4.5", 2000, 300) == 0.0035


def test_no_model_or_a_model_on_your_own_machine_costs_nothing():
    assert request_cost(None, 2000, 300) == 0.0
    assert request_cost("ollama/llama3.2:3b", 2000, 300) == 0.0


def test_missing_token_counts_count_as_zero():
    assert request_cost("openai/gpt-4.1-mini", None, 1000) == 0.0016
    assert request_cost("openai/gpt-4.1-mini", 1000, None) == 0.0004


def test_an_unknown_model_is_an_error_not_a_free_answer():
    with pytest.raises(KeyError, match="no price for some/new-model"):
        request_cost("some/new-model", 100, 100)


def test_every_answer_carries_its_cost(monkeypatch):
    """The real path, with a scripted model that reports its token usage."""
    monkeypatch.delenv("CHAT_FAKE", raising=False)
    monkeypatch.delenv("ROUTING", raising=False)
    monkeypatch.delenv("CACHE", raising=False)
    chunk = {"text": "x", "source": "vpn.pdf", "page": 1, "score": 0.8}
    monkeypatch.setattr(
        service,
        "find",
        lambda q: {"query": q, "kept": [chunk], "sources": ["vpn.pdf, page 1"]},
    )
    usage = SimpleNamespace(prompt_tokens=1800, completion_tokens=40, total_tokens=1840)
    stream = [
        SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="12 hours [1]."))],
            usage=None,
        ),
        SimpleNamespace(choices=[], usage=usage),
    ]
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **k: iter(stream))
        )
    )
    monkeypatch.setattr(service, "model_client", lambda: client)
    r = service.answer("How long can a VPN session stay connected?")
    price = PRICES[MODEL]
    assert (r["prompt_tokens"], r["completion_tokens"]) == (1800, 40)
    assert r["cost_usd"] == round(
        (1800 * price["input"] + 40 * price["output"]) / 1_000_000, 6
    )
