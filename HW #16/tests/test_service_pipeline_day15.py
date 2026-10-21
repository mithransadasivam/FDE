"""Day 15 end-to-end checks (updated on Day 16: the answer now also has its tokens, cost and route) of the real (not fake) path, with a scripted streaming model: the class
sources, the token count from the stream, and a real connection error answered by the fallback."""

from types import SimpleNamespace

import httpx
import openai
import pytest

from app import service
from app.rag import MODEL

SOURCES = ["Day06_Slide15_policy_vpn_remote_access.pdf, page 1"]


def chunk(text=None, total=None):
    choices = (
        [SimpleNamespace(delta=SimpleNamespace(content=text))]
        if text is not None
        else []
    )
    usage = SimpleNamespace(total_tokens=total) if total else None
    return SimpleNamespace(choices=choices, usage=usage)


class ScriptedClient:
    """Streams a fixed reply; raises a connection error for every model in `down`."""

    def __init__(self, down=()):
        self.down, self.models = set(down), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, model, stream, **kwargs):
        self.models.append(model)
        assert stream is True and kwargs["stream_options"] == {"include_usage": True}
        if model in self.down:
            raise openai.APIConnectionError(
                request=httpx.Request("POST", "https://openrouter.ai")
            )
        return iter(
            [
                chunk("A VPN session lasts at most "),
                chunk("12 hours [1]."),
                chunk(total=812),
            ]
        )


@pytest.fixture
def real_path(monkeypatch, tmp_path):
    monkeypatch.delenv("CHAT_FAKE", raising=False)
    monkeypatch.delenv("SIMULATE_OUTAGE", raising=False)
    monkeypatch.setattr(
        service,
        "find",
        lambda q: {
            "query": q,
            "kept": [{"text": "x", "source": "vpn.pdf", "page": 1}],
            "sources": SOURCES,
        },
    )
    monkeypatch.setattr("app.reliability.time.sleep", lambda s: None)


def test_the_real_path_streams_the_answer_and_counts_tokens(real_path, monkeypatch):
    client = ScriptedClient()
    monkeypatch.setattr(service, "model_client", lambda: client)
    r = service.answer("How long can a VPN session stay connected?")
    expected = {
        "answer": "A VPN session lasts at most 12 hours [1].",
        "sources": SOURCES,
        "declined": False,
        "model": MODEL,
        "fallback": False,
        "tokens": 812,
    }
    assert {k: r[k] for k in expected} == expected


def test_a_provider_outage_is_answered_by_the_fallback_model(real_path, monkeypatch):
    client = ScriptedClient(down={MODEL})
    monkeypatch.setattr(service, "model_client", lambda: client)
    r = service.answer("How long can a VPN session stay connected?")
    assert r["model"] == service.FALLBACK_MODEL and r["fallback"] is True
    assert client.models == [MODEL] * 3 + [service.FALLBACK_MODEL]
