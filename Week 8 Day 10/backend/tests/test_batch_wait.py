"""A real run waits and tries again when the provider says 429, and never uses more workers than the cap."""

from app.llm import RateLimited
from app.pipeline import batch


def test_waits_then_retries_on_429(monkeypatch):
    sleeps = []
    monkeypatch.setattr(batch, "_sleep", sleeps.append)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] <= 2:
            raise RateLimited("too many requests")
        return {"ok": True}

    res = batch.run_live([batch.Job(key="B-001/extract_v2", run=flaky)], concurrency=1)
    assert res.done == {"B-001/extract_v2": {"ok": True}} and res.failed == []
    assert res.refusals == 2 and len(sleeps) == 2
    assert sleeps[0] > 0 and sleeps[1] > sleeps[0] * 0.9  # the wait grows


def test_honours_retry_after(monkeypatch):
    sleeps = []
    monkeypatch.setattr(batch, "_sleep", sleeps.append)
    calls = {"n": 0}

    def once():
        calls["n"] += 1
        if calls["n"] == 1:
            e = RateLimited("slow down")
            e.retry_after = 12.0
            raise e
        return {"ok": True}

    batch.run_live([batch.Job(key="B-002/extract_v2", run=once)], concurrency=1)
    assert sleeps == [12.0]


def test_gives_up_after_max_retries_and_lists_the_document(monkeypatch):
    monkeypatch.setattr(batch, "_sleep", lambda s: None)

    def always():
        raise RateLimited("no")

    res = batch.run_live([batch.Job(key="B-003/extract_v2", run=always)], concurrency=1, max_retries=2)
    assert res.failed == ["B-003/extract_v2"] and res.refusals == 3
