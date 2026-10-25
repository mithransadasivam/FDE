"""Fixtures. No test calls a real model or the network: the API key is removed and outgoing requests are blocked.
Every test gets a temporary database and a fake model with no delay."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tower.llm import FakeLLM  # noqa: E402
from tower.models import Alert  # noqa: E402
from tower.settings import Settings  # noqa: E402
from tower.tower import Tower  # noqa: E402


@pytest.fixture(autouse=True)
def no_network_no_key(monkeypatch):
    for k in ("OPENROUTER_API_KEY", "MODEL_MODE", "PHOENIX_COLLECTOR_ENDPOINT"):
        monkeypatch.delenv(k, raising=False)
    import requests

    def blocked(*a, **k):
        raise AssertionError("a test tried to use the network")

    monkeypatch.setattr(requests.sessions.Session, "request", blocked)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(db_path=tmp_path / "t.db", actions_log=tmp_path / "actions.log", app_log=tmp_path / "tower.log",
                    model_mode="fake", fake_latency_scale=0.0, admin_debug=True)


@pytest.fixture
def tower(settings) -> Tower:
    return Tower(settings, FakeLLM(settings, latency_scale=0))


@pytest.fixture
def triaged(tower) -> Tower:
    tower.triage()
    return tower


def mk(alert_id, time, service, check="http_check", severity="major", status="firing", message="Response time 9 s", source="monitor"):
    return Alert(alert_id=alert_id, time=time, source=source, service=service, check=check, severity=severity, status=status, message=message)
