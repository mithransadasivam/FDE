import pytest
import requests

from app import llm


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status = payload, status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f"HTTP {self.status}")

    def json(self):
        return self.payload


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-SECRET-123")
    monkeypatch.setenv("LLM_MODEL", "test/model")


def reply(text):
    return FakeResponse({"choices": [{"message": {"content": text}}]})


def test_sends_timeout_max_tokens_and_returns_text(monkeypatch, configured):
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, json=json, timeout=timeout)
        return reply("  hello [1]  ")

    monkeypatch.setattr(llm.requests, "post", fake_post)
    assert llm.call_model([{"role": "user", "content": "hi"}]) == "hello [1]"
    assert seen["timeout"] > 0 and seen["json"]["max_tokens"] > 0
    assert seen["json"]["model"] == "test/model" and seen["url"].startswith("https://")


def test_missing_configuration_gives_friendly_error():
    with pytest.raises(llm.LLMError, match="not configured"):
        llm.call_model([])


@pytest.mark.parametrize("bad", [
    FakeResponse({"choices": [{"message": {"content": None}}]}),   # refusal with null content
    FakeResponse({"choices": [{"message": {"content": "   "}}]}),  # blank
    FakeResponse({"choices": [{"message": {"content": 42}}]}),     # wrong type
    FakeResponse({"choices": []}),
    FakeResponse({"unexpected": True}),
    FakeResponse({}, status=500),
])
def test_bad_replies_become_llm_error(monkeypatch, configured, bad):
    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: bad)
    with pytest.raises(llm.LLMError):
        llm.call_model([])


def test_network_failure_error_never_contains_the_key(monkeypatch, configured):
    def boom(*a, **k):
        raise requests.ConnectionError("failed for Bearer sk-test-SECRET-123")

    monkeypatch.setattr(llm.requests, "post", boom)
    with pytest.raises(llm.LLMError) as info:
        llm.call_model([])
    assert "SECRET" not in str(info.value)
    assert "ConnectionError" in str(info.value)


def test_conftest_blocks_real_network_calls():
    with pytest.raises(AssertionError, match="real network call"):
        requests.post("https://openrouter.ai/api/v1/chat/completions")


def test_conftest_hides_the_real_key():
    import os

    assert os.getenv("OPENROUTER_API_KEY") is None
