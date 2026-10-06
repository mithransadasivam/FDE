"""Project settings in one place."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "data" / "docs"

# Chunking: 500 characters is a few sentences (enough to hold one fact with its
# context); 100 characters of overlap stops a fact being cut in half at a boundary.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

# Embeddings (local Ollama) and vector database
OLLAMA_URL = "http://localhost:11434"
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
