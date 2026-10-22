"""Day 16, Activity 2: ResponseCache.get() serves a saved answer, and never an expired one."""

from fastapi.testclient import TestClient

from app.api import api
from app.cache import ResponseCache, cache_key


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_an_unknown_key_is_a_miss(tmp_path):
    assert ResponseCache(str(tmp_path / "c.sqlite")).get("nothing-here") is None


def test_a_saved_answer_comes_back_marked_cached_and_counted(tmp_path):
    cache = ResponseCache(str(tmp_path / "c.sqlite"))
    cache.put("k1", {"answer": "12 hours [1].", "model": "m"})
    assert cache.get("k1") == {"answer": "12 hours [1].", "model": "m", "cached": True}
    cache.get("k1")
    assert cache.stats() == {"entries": 1, "hits": 2}


def test_an_expired_answer_is_deleted_and_never_served(tmp_path):
    clock = Clock()
    cache = ResponseCache(str(tmp_path / "c.sqlite"), ttl=60, clock=clock)
    cache.put("k1", {"answer": "old"})
    clock.now += 60
    assert cache.get("k1") is not None  # exactly 60 seconds old: still fresh
    clock.now += 1
    assert cache.get("k1") is None
    assert cache.stats()["entries"] == 0


def test_the_same_question_spelled_differently_has_the_same_key():
    a = cache_key("How long can a VPN session stay connected?", "rag-1")
    assert a == cache_key("  how long can a vpn session   stay connected?? ", "rag-1")
    assert a != cache_key("How long can a VPN session stay connected?", "rag-2")


def test_the_second_ask_comes_from_the_cache_and_costs_nothing(
    fake_chatbot, fresh_cache, monkeypatch
):
    monkeypatch.setenv("CACHE", "1")
    client = TestClient(api)
    first = client.post(
        "/ask", json={"question": "How often are laptops replaced?"}
    ).json()
    second = client.post(
        "/ask", json={"question": "how often are laptops replaced"}
    ).json()
    assert first["cached"] is False and second["cached"] is True
    assert second["answer"] == first["answer"] and second["cost_usd"] == 0.0
    assert second["completion_tokens"] == 0 and fresh_cache.stats()["hits"] == 1
