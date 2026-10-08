import pytest

from app.retriever import search
from app.store import build_index

# Tiny fake "embedding": a 3-number vector chosen by keyword, so no real model is needed.
def fake_embed_text(text):
    t = text.lower()
    return [1.0 if "vpn" in t else 0.0, 1.0 if "backup" in t else 0.0, 0.1]


def fake_embed_many(texts):
    return [fake_embed_text(t) for t in texts]


CHUNKS = [
    {"source": "vpn.md", "page": 1, "chunk": 1, "text": "vpn setup steps"},
    {"source": "backup.md", "page": 2, "chunk": 1, "text": "backup runs daily"},
    {"source": "misc.md", "page": 1, "chunk": 1, "text": "something else entirely"},
]


@pytest.fixture
def index(tmp_path):
    build_index(CHUNKS, fake_many := fake_embed_many, tmp_path)
    return tmp_path


def test_best_match_first_with_source_page_score(index):
    results = search("my vpn fails", k=3, embed_fn=fake_embed_text, path=index)
    assert results[0]["source"] == "vpn.md" and results[0]["page"] == 1
    assert set(results[0]) == {"text", "source", "page", "chunk", "score"}
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_k_limits_results(index):
    assert len(search("backup", k=1, embed_fn=fake_embed_text, path=index)) == 1


def test_k_larger_than_index_is_fine(index):
    assert len(search("backup", k=10, embed_fn=fake_embed_text, path=index)) == 3


def test_blank_question_returns_nothing(index):
    assert search("   ", embed_fn=fake_embed_text, path=index) == []


def test_invalid_k_raises(index):
    with pytest.raises(ValueError):
        search("vpn", k=0, embed_fn=fake_embed_text, path=index)


def test_missing_index_raises(tmp_path):
    with pytest.raises(ValueError):
        search("vpn", embed_fn=fake_embed_text, path=tmp_path)
