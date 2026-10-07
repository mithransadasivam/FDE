"""The persistent ChromaDB collection that holds every chunk."""
from pathlib import Path

import chromadb

from app.config import CHROMA_DIR, COLLECTION_NAME


def _client(path: Path):
    return chromadb.PersistentClient(path=str(path))


def _delete_if_exists(client, name: str) -> None:
    try:
        client.delete_collection(name)
    except Exception:  # it was not there
        pass


def build_index(chunks: list[dict], embed_fn, path: Path = CHROMA_DIR, name: str = COLLECTION_NAME) -> int:
    """Rebuild the collection from scratch. `embed_fn(list[str]) -> list[vector]`.

    The new index is built under a temporary name and only swapped in once every
    embedding has succeeded, so a failure (Ollama down) leaves the old index intact.
    Returns the number of chunks stored.
    """
    client = _client(path)
    vectors = embed_fn([c["text"] for c in chunks]) if chunks else []  # may raise: nothing changed yet

    temp = f"{name}__new"
    _delete_if_exists(client, temp)
    collection = client.create_collection(temp, metadata={"hnsw:space": "cosine"})
    try:
        if chunks:
            collection.add(
                ids=[f"{c['source']}::{c['chunk']}" for c in chunks],
                documents=[c["text"] for c in chunks],
                embeddings=vectors,
                metadatas=[{"source": c["source"], "page": c["page"], "chunk": c["chunk"]} for c in chunks],
            )
        count = collection.count()
        _delete_if_exists(client, name)
        collection.modify(name=name)
    except Exception:
        _delete_if_exists(client, temp)
        raise
    return count


def get_collection(path: Path = CHROMA_DIR, name: str = COLLECTION_NAME):
    """Open the saved collection. Raises ValueError if the index was never built."""
    try:
        return _client(path).get_collection(name)
    except Exception as err:
        raise ValueError("The index has not been built yet. Run scripts/build_index.") from err


def count_chunks(path: Path = CHROMA_DIR, name: str = COLLECTION_NAME) -> int:
    """Number of chunks stored on disk. Does not call the embedding model."""
    return get_collection(path, name).count()
