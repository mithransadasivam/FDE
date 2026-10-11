"""Project settings in one place."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Where the knowledge base lives. The browser tests point these at throwaway folders so that adding a document in a test never touches the real one.
DOCS_DIR = Path(os.getenv("KB_DOCS_DIR", ROOT / "data" / "docs"))
TRANSCRIPTS_DIR = Path(os.getenv("KB_TRANSCRIPTS_DIR", ROOT / "data" / "transcripts"))  # what the vision model read from scanned pages

# Chunking: 500 characters is a few sentences (enough to hold one fact with its
# context); 100 characters of overlap stops a fact being cut in half at a boundary.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

# Embeddings (local Ollama) and vector database
OLLAMA_URL = "http://127.0.0.1:11434"  # not "localhost": on Windows that adds about 2 seconds to every call
EMBED_MODEL = "nomic-embed-text"
EMBED_TIMEOUT = 60  # seconds
EMBED_KEEP_ALIVE = "30m"  # keep the embedding model loaded between questions, so a quiet spell does not cause a slow reload
CHROMA_DIR = Path(os.getenv("KB_CHROMA_DIR", ROOT / "data" / "chroma"))
COLLECTION_NAME = os.getenv("KB_COLLECTION", "it_helpdesk")

# Retrieval: 4 chunks gives enough context for one answer without much noise or cost.
TOP_K = 4

# Answers
# Guard 1: below this similarity no chunk counts as relevant (0.51 for an unrelated
# question, 0.61 for the lowest real answer in the first test). Tuned in Phase 7.
MIN_SCORE = 0.0  # DEMO BREAK: Guard 1 never declines
# Low temperature: answers should stay close to the sources and be repeatable.
TEMPERATURE = 0.1
MAX_TOKENS = 400
JUDGE_TEMPERATURE = 0.0  # a judge should give the same verdict every time
JUDGE_MAX_TOKENS = 400
# Images (Day 10 exercise): what a user may attach, and how small an image is made before it goes to the vision model.
IMAGE_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
IMAGE_MAX_BYTES = 5 * 1024 * 1024  # a bigger file is refused before anything is sent anywhere
IMAGE_MAX_SIDE = 1024              # pixels on the longest side; chosen by measurement in Phase 39
VISION_MAX_TOKENS = 300
# Scanned pages (picture-only PDF pages) are read by the vision model once and the text is saved (data/transcripts).
SCAN_RENDER_SIDE = 1600       # pixels on the longest side when a page is turned into a picture to be read
SCAN_MAX_TOKENS = 1500        # the longest transcription of one page
MAX_VISION_PAGES = 6          # an upload that needs more vision calls than this asks the user to confirm first
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
VISION_PAGE_COST_USD = 0.004  # a rough price of reading one page (about 1,700 tokens in and 400 out at the vision model's price); only for the warning
IMAGE_THUMBNAIL_SIDE = 240         # the small preview kept in the chat while the page is open (never written to disk)
MAX_QUESTION_CHARS = 500  # longer messages are shortened to their end (where the question usually is) before any search
MAX_INPUT_CHARS = 100_000  # a message longer than this is refused outright: pasting that much is almost certainly a mistake
LLM_TIMEOUT = 60  # seconds
# A made-up code word that sits in the chatbot's instructions and has no other purpose. If it ever appears in a reply,
# the instructions have leaked, and the reply is blocked. Tests look for it too.
CANARY = "CANARY-7Q2X"
REFUSAL_SENTENCE = (
    "I can't help with that request, because it would get round a security control or expose someone else's data. "
    "If you have a genuine need, please contact the service desk on extension 4357 or servicedesk@northwind.example."
)
DECLINE_SENTENCE = (
    "I don't know: the documents don't cover that. "
    "Please contact the service desk on extension 4357 or servicedesk@northwind.example."
)

# Retrieval mode used by the chatbot: vector, hybrid, rerank or full (see app/retrieval.py).
# The saved choice is made in Phase 14. For an experiment you can override it for one run
# without editing this file, e.g. `set RETRIEVAL_MODE=full` before starting the app.
RETRIEVAL_MODES = ("vector", "hybrid", "rerank", "full", "smart")
RETRIEVAL_MODE = os.getenv("RETRIEVAL_MODE", "smart")
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
# A fake chatbot for fast, repeatable browser tests (Day 9 exercise, Phase 29): fixed topics, fixed sources, no models, no Ollama.
# Off by default. `set CHAT_FAKE=1` before starting the app. A banner on every page says when it is on.
CHAT_FAKE = os.getenv("CHAT_FAKE", "0") == "1"
CHAT_FAKE_DELAY = float(os.getenv("CHAT_FAKE_DELAY", "0.05"))  # seconds between streamed pieces, so streaming still happens

# Self-critique (Day 8 exercise, Phase 24): off by default. `set SELF_CRITIQUE=1` turns it on for a run.
SELF_CRITIQUE = os.getenv("SELF_CRITIQUE", "0") == "1"
SELF_CRITIQUE_MAX_RETRIES = 2  # at most this many regenerations per answer
P95_TARGET_SECONDS = 5.0  # Day 8 exercise, set before measuring: 95 of 100 whole answers must be at least this fast

# Query rewriting: a rewritten query longer than this is not trusted; the original question is used.
REWRITE_MAX_CHARS = 200

# Voice (Phase 37): a spoken question is turned into text first, then follows the same path as a typed one
AUDIO_TYPES = ("wav", "mp3", "ogg", "webm", "m4a", "flac")
AUDIO_MAX_BYTES = 5 * 1024 * 1024  # a bigger file is refused before it is sent anywhere
AUDIO_MAX_SECONDS = 60             # checked exactly for WAV; other formats are held to the size limit
SILENCE_LEVEL = 150                # a recording whose loudest sound stays under this (out of 32768) counts as silent: no call is made
STT_PRICE_PER_MINUTE = 0.006       # US dollars per minute of audio, for the cost line only

# Pictures out (Phase 38): off unless the person presses the button, and only a one-sentence summary is ever sent
ILLUSTRATION_STYLE = "A simple flat illustration, soft colours. No text, no letters, no numbers, no logos, no people, no faces."
ILLUSTRATION_SUMMARY_CHARS = 200
IMAGE_COST_USD = 0.04  # a rough price of one generated picture, for the cost line only
ILLUSTRATIONS_ENABLED = os.getenv("ILLUSTRATIONS", "0") == "1"  # off unless switched on in .env or the environment: no button, no picture calls
