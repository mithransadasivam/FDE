"""Day 16 test helpers: `fresh_cache`, an empty response cache in a temporary file."""

import pytest


@pytest.fixture
def fresh_cache(tmp_path, monkeypatch):
    from app import service
    from app.cache import ResponseCache

    cache = ResponseCache(str(tmp_path / "responses.sqlite"))
    monkeypatch.setattr(service, "_cache", cache)
    return cache
