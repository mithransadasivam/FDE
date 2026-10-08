"""Embeddings from the local Ollama model. Same model for documents and questions."""
import numpy as np
import requests

from app.config import EMBED_MODEL, EMBED_TIMEOUT, OLLAMA_URL

# nomic-embed-text is trained with these task prefixes; using them helps matching.
DOC_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "


class EmbeddingError(RuntimeError):
    """Ollama is unreachable or returned something unusable."""


def _embed(texts: list[str]) -> list[list[float]]:
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": EMBED_MODEL, "input": texts},
            timeout=EMBED_TIMEOUT,
        )
        resp.raise_for_status()
        vectors = resp.json()["embeddings"]
    except (requests.RequestException, KeyError, ValueError) as err:
        raise EmbeddingError(
            f"Could not get embeddings from Ollama ({type(err).__name__}). "
            f"Is Ollama running with the '{EMBED_MODEL}' model?"
        ) from err
    if len(vectors) != len(texts):
        raise EmbeddingError("Ollama returned the wrong number of embeddings.")
    return vectors


def embed_documents(texts: list[str], batch_size: int = 16) -> list[list[float]]:
    """Embed document chunks (in small batches)."""
    vectors = []
    for i in range(0, len(texts), batch_size):
        batch = [DOC_PREFIX + t for t in texts[i:i + batch_size]]
        vectors.extend(_embed(batch))
    return vectors


def embed_query(question: str, client=None) -> list[float]:
    """Embed one question. `client` is accepted for Day 7 tests with a fake; it is not needed."""
    return _embed([QUERY_PREFIX + question])[0]


def cosine_similarity(a, b) -> float:
    """Cosine similarity of two vectors (1.0 = same direction)."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
