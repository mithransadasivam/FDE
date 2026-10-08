"""Safety net for every test: no real network calls and no real API key.

If a test forgets to use a fake model or embedder, it fails loudly here instead of
quietly calling OpenRouter or Ollama with the real key from .env.
"""
import pytest
import requests


class NetworkBlocked(AssertionError):
    pass


@pytest.fixture(autouse=True)
def no_network_and_no_keys(monkeypatch):
    def blocked(*args, **kwargs):
        raise NetworkBlocked("A test tried to make a real network call. Use a fake instead.")

    # Tests that need requests.post set their own fake AFTER this fixture runs.
    for name in ("get", "post", "put", "delete", "request"):
        monkeypatch.setattr(requests, name, blocked)
    monkeypatch.setattr(requests.Session, "send", blocked)

    # The real key must never be visible to a test, and .env must not be loaded.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setattr("app.llm.load_dotenv", lambda *a, **k: False)
