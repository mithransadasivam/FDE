"""Safety net for every test: no real network, no real API key, no real database.

A test that forgets to use a fake model fails loudly here instead of quietly calling OpenRouter. Every test gets
a temporary database, a temporary request log and temporary runs folder.
"""
import socket

import pytest
import requests


class NetworkBlocked(AssertionError):
    pass


@pytest.fixture(autouse=True)
def no_network_and_no_keys(monkeypatch):
    def blocked(*a, **k):
        raise NetworkBlocked("A test tried to make a real network call. Use a fake model instead.")

    for name in ("get", "post", "put", "delete", "request"):
        monkeypatch.setattr(requests, name, blocked)
    monkeypatch.setattr(requests.Session, "send", blocked)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A fresh fictional vendor database in a temporary folder; the real data/procurement.db is never touched."""
    from vendor_desk import db as dbmod
    path = tmp_path / "procurement.db"
    dbmod.build_database(path)
    monkeypatch.setenv("VENDOR_DB", str(path))
    monkeypatch.setenv("MCP_QUERY_LOG", str(tmp_path / "mcp_query_log.jsonl"))
    return path


@pytest.fixture
def runs(tmp_path, monkeypatch):
    from vendor_desk import config
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")
    return tmp_path / "runs"
