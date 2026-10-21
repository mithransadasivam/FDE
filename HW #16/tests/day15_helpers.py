"""Day 15 test helpers: `fake_chatbot`, the service in CHAT_FAKE mode with its own request log."""

import pytest


@pytest.fixture
def fake_chatbot(tmp_path, monkeypatch):
    """The fake chatbot (no Ollama, no key, no pauses) logging to a temporary file. Yields the log path."""
    import app.chat_fake
    import app.monitoring

    log = tmp_path / "logs" / "requests.jsonl"
    monkeypatch.setenv("CHAT_FAKE", "1")
    monkeypatch.delenv("SIMULATE_OUTAGE", raising=False)
    monkeypatch.setattr(app.monitoring, "REQUEST_LOG", str(log))
    monkeypatch.setattr(app.monitoring, "ALERT_RULES", str(tmp_path / "no_rules.json"))
    monkeypatch.setattr(app.chat_fake.time, "sleep", lambda s: None)
    monkeypatch.setattr("app.reliability.time.sleep", lambda s: None)
    yield log
