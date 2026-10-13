import pytest
import requests

from app import embeddings
from app.store import build_index, count_chunks, get_collection


def fake_embed(texts):
    return [[float(len(t)), 1.0, 0.5] for t in texts]


CHUNKS = [
    {"source": "a.md", "page": 1, "chunk": 1, "text": "first chunk"},
    {"source": "a.md", "page": 2, "chunk": 2, "text": "second chunk"},
    {"source": "b.md", "page": 1, "chunk": 1, "text": "third chunk"},
]


def test_build_stores_chunks_with_metadata(tmp_path):
    assert build_index(CHUNKS, fake_embed, tmp_path) == 3
    got = get_collection(tmp_path).get(include=["metadatas", "documents"])
    assert sorted(m["source"] for m in got["metadatas"]) == ["a.md", "a.md", "b.md"]
    assert {"source", "page", "chunk"} == set(got["metadatas"][0])


def test_count_survives_restart_without_embedding(tmp_path):
    build_index(CHUNKS, fake_embed, tmp_path)
    # a fresh client reads the data from disk; no embedding function is involved
    assert count_chunks(tmp_path) == 3


def test_rebuild_replaces_old_content(tmp_path):
    build_index(CHUNKS, fake_embed, tmp_path)
    assert build_index(CHUNKS[:1], fake_embed, tmp_path) == 1
    assert count_chunks(tmp_path) == 1


def test_count_before_build_raises(tmp_path):
    with pytest.raises(ValueError):
        count_chunks(tmp_path)


def test_ollama_down_gives_friendly_error(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(embeddings.requests, "post", boom)
    with pytest.raises(embeddings.EmbeddingError, match="Ollama"):
        embeddings.embed_query("hello")


def test_failed_embedding_leaves_the_old_index_untouched(tmp_path):
    build_index(CHUNKS, fake_embed, tmp_path)

    def broken(texts):
        raise RuntimeError("Ollama is down")

    with pytest.raises(RuntimeError):
        build_index(CHUNKS[:1], broken, tmp_path)
    assert count_chunks(tmp_path) == 3  # the old index survived


def test_failure_while_adding_cleans_up_and_keeps_old_index(tmp_path):
    build_index(CHUNKS, fake_embed, tmp_path)
    with pytest.raises(Exception):
        build_index(CHUNKS[:2], lambda texts: [[1.0, 1.0, 1.0]], tmp_path)  # 1 vector for 2 chunks
    assert count_chunks(tmp_path) == 3
    import chromadb

    names = [c.name if hasattr(c, "name") else c for c in chromadb.PersistentClient(path=str(tmp_path)).list_collections()]
    assert names == ["it_helpdesk"]  # no leftover temporary collection


def test_rebuild_with_no_chunks_gives_an_empty_index(tmp_path):
    build_index(CHUNKS, fake_embed, tmp_path)
    assert build_index([], fake_embed, tmp_path) == 0
    assert count_chunks(tmp_path) == 0
