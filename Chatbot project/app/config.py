"""Project settings in one place."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "data" / "docs"

# Chunking: 500 characters is a few sentences (enough to hold one fact with its
# context); 100 characters of overlap stops a fact being cut in half at a boundary.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

# Embeddings (local Ollama) and vector database
OLLAMA_URL = "http://127.0.0.1:11434"  # not "localhost": on Windows that adds about 2 seconds to every call
EMBED_MODEL = "nomic-embed-text"
EMBED_TIMEOUT = 60  # seconds
CHROMA_DIR = ROOT / "data" / "chroma"
COLLECTION_NAME = "it_helpdesk"

# Retrieval: 4 chunks gives enough context for one answer without much noise or cost.
TOP_K = 4

# Answers
# Guard 1: below this similarity no chunk counts as relevant (0.51 for an unrelated
# question, 0.61 for the lowest real answer in the first test). Tuned in Phase 7.
MIN_SCORE = 0.55
# Low temperature: answers should stay close to the sources and be repeatable.
TEMPERATURE = 0.1
MAX_TOKENS = 400
MAX_QUESTION_CHARS = 500  # longer questions are refused before any embedding or model call
LLM_TIMEOUT = 60  # seconds
DECLINE_SENTENCE = (
    "I don't know: the documents don't cover that. "
    "Please contact the service desk on extension 4357 or servicedesk@northwind.example."
)

# Retrieval mode used by the chatbot: vector, hybrid, rerank or full (see app/retrieval.py).
# The saved choice is made in Phase 14. For an experiment you can override it for one run
# without editing this file, e.g. `set RETRIEVAL_MODE=full` before starting the app.
RETRIEVAL_MODES = ("vector", "hybrid", "rerank", "full")
RETRIEVAL_MODE = os.getenv("RETRIEVAL_MODE", "vector")
if RETRIEVAL_MODE not in RETRIEVAL_MODES:
    raise ValueError(f"RETRIEVAL_MODE must be one of {', '.join(RETRIEVAL_MODES)} (got '{RETRIEVAL_MODE}')")
# Hybrid search: how many candidates each search (meaning-based and keyword) contributes before fusing.
HYBRID_CANDIDATES = 10
# Reranking: how many candidates the model judges in its one call. More can rescue a lower-ranked
# right chunk, but costs more time and tokens.
RERANK_CANDIDATES = 10
# The retrieval target, set before any measurements existed (Phase 14).
TARGET_HIT_RATE = 0.90
TARGET_SECONDS = 3.0  # a whole answer, as the user feels it: retrieval plus the model writing the reply

# Query rewriting: a rewritten query longer than this is not trusted; the original question is used.
REWRITE_MAX_CHARS = 200
