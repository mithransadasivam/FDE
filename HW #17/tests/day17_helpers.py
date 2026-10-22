"""Day 17 test helpers: `red_team_env`, the fake chatbot and the fake agent with a fresh database."""

import pytest


@pytest.fixture
def red_team_env(fake_chatbot, db, monkeypatch):
    """CHAT_FAKE=1 (the gullible fake), no cache, guardrails off, and data/helpdesk.db replaced by a
    fresh copy in a temporary folder. Turn guardrails on with monkeypatch.setenv("GUARDRAILS", "1")."""
    import app.tools

    monkeypatch.setenv("CACHE", "0")
    monkeypatch.setenv("GUARDRAILS", "0")
    monkeypatch.setattr(app.tools, "DB_PATH", db)
    yield db
