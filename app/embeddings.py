"""Day 6: turn text into embeddings with a local model, and compare them.

The embeddings come from Ollama on your laptop (the nomic-embed-text model): free and private.
embed_documents() and embed_query() are done.
Activity 1: fill in cosine_similarity(). Check it with tests/test_similarity.py.
"""

import os

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")


def embedding_client() -> OpenAI:
    # Same code as Day 3, different base URL: Ollama on this machine
    return OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")


def _embed(texts, client=None) -> np.ndarray:
    client = client or embedding_client()
    r = client.embeddings.create(model=EMBED_MODEL, input=list(texts))
    return np.array([d.embedding for d in r.data], dtype=float)


def embed_documents(texts, client=None) -> np.ndarray:
    """One vector per text. nomic-embed-text works best with this prefix on stored text."""
    return _embed([f"search_document: {t}" for t in texts], client)


def embed_query(text: str, client=None) -> np.ndarray:
    """One vector for a question. nomic-embed-text works best with this prefix on questions."""
    return _embed([f"search_query: {text}"], client)[0]


def cosine_similarity(a, b) -> float:
    """TODO (Activity 1): how closely two vectors point in the same direction.

    1.0 means the same direction (same meaning), 0 means unrelated, -1 means opposite.
    Formula: the dot product of a and b, divided by (the length of a x the length of b).
    Use numpy: np.dot(a, b) and np.linalg.norm(a). Return a plain float.
    """
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
