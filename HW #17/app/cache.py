"""Day 16: a response cache. The same question asked again gets the saved answer at once: no
retrieval, no model call, no cost.

The key is the normalised question plus everything that would change the answer: the prompt
version and the models in use. A changed prompt or model therefore never serves an old answer.
Entries expire after CACHE_TTL_SECONDS, so answers follow updated documents within a day.

Done: normalise_question(), cache_key(), ResponseCache (put(), clear(), stats()).
Activity 2: fill in ResponseCache.get(). Check it with tests/test_cache.py.
"""

import hashlib
from contextlib import closing
import json
import os
import re
import sqlite3
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
CACHE_PATH = os.getenv("CACHE_PATH", "cache/responses.sqlite")
CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "86400"))  # one day


def normalise_question(question: str) -> str:
    """Lower case, single spaces, no punctuation at the end: "How long, VPN?? " -> "how long, vpn"."""
    return re.sub(r"\s+", " ", question).strip().lower().rstrip("?!. ")


def cache_key(question: str, *parts: str) -> str:
    """A short fingerprint of the normalised question and the other parts (prompt version, models)."""
    text = "|".join([normalise_question(question), *parts])
    return hashlib.sha256(text.encode()).hexdigest()[:32]


class ResponseCache:
    """Answers saved in a small SQLite file: key, answer (JSON), when it was saved, how often used."""

    def __init__(self, path: str = CACHE_PATH, ttl: int = CACHE_TTL, clock=time.time):
        self.path, self.ttl, self.clock = path, ttl, clock
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS answers (key TEXT PRIMARY KEY, answer TEXT, "
                "saved_at REAL, hits INTEGER DEFAULT 0)"
            )

    def _db(self):
        return sqlite3.connect(self.path, timeout=30)

    def put(self, key: str, answer: dict) -> None:
        with self._db() as db:
            db.execute(
                "INSERT OR REPLACE INTO answers (key, answer, saved_at, hits) VALUES (?, ?, ?, 0)",
                (key, json.dumps(answer), self.clock()),
            )

    def get(self, key: str) -> dict | None:
        """TODO (Activity 2): the saved answer for this key, or None.

        Rules (tests/test_cache.py checks each one):
        - look up the row for key in the answers table (SELECT answer, saved_at ... WHERE key = ?)
        - no row: return None
        - the row is older than self.ttl seconds (self.clock() - saved_at > self.ttl):
          delete it and return None, so an old answer is never served
        - otherwise add 1 to its hits, and return the saved answer (json.loads) with "cached": True
        """
        with closing(self._db()) as db, db:
            row = db.execute(
                "SELECT answer, saved_at FROM answers WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                return None
            answer, saved_at = row
            if self.clock() - saved_at > self.ttl:
                db.execute("DELETE FROM answers WHERE key = ?", (key,))
                return None
            db.execute("UPDATE answers SET hits = hits + 1 WHERE key = ?", (key,))
        return {**json.loads(answer), "cached": True}

    def clear(self) -> int:
        with self._db() as db:
            return db.execute("DELETE FROM answers").rowcount

    def stats(self) -> dict:
        with self._db() as db:
            n, hits = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(hits), 0) FROM answers"
            ).fetchone()
        return {"entries": n, "hits": hits}
