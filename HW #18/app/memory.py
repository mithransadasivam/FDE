"""Day 12: the agent's notebook. Notes are its working memory during a run, and its long-term memory
across runs when the notebook is saved to a file.

Done: add(), all(), save(), load and memory_context().
Activity 2: fill in search(). Check it with tests/test_memory.py.
"""

import json
import re
from datetime import datetime
from pathlib import Path

STOPWORDS = {
    "the",
    "and",
    "for",
    "are",
    "was",
    "were",
    "what",
    "which",
    "how",
    "many",
    "much",
    "does",
    "did",
    "this",
    "that",
    "these",
    "those",
    "with",
    "about",
    "from",
    "our",
    "your",
    "their",
    "there",
    "have",
    "has",
    "had",
    "any",
    "all",
    "can",
    "should",
    "would",
    "could",
    "tell",
    "users",
    "user",
    "still",
}


def words(text: str) -> set[str]:
    """The meaningful words in a text: lower case, letters and digits, at least 3 long, no stop words.
    A code such as VPN-809 is kept whole."""
    return {
        w
        for w in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower())
        if len(w) >= 3 and w not in STOPWORDS
    }


class NoteBook:
    """A list of notes, each {"text", "source", "saved"}. Give a path to keep them between runs."""

    def __init__(self, path: str | None = None):
        self.path = path
        self.notes = []
        if path and Path(path).exists():
            self.notes = json.loads(Path(path).read_text(encoding="utf-8"))

    def add(self, text: str, source: str) -> dict:
        """Save one fact with where it came from. The same text is never saved twice."""
        text, source = text.strip(), source.strip()
        if not text or not source:
            raise ValueError("a note needs both text and a source")
        if any(n["text"].lower() == text.lower() for n in self.notes):
            return {"saved": False, "reason": "already noted", "count": len(self.notes)}
        self.notes.append(
            {
                "text": text,
                "source": source,
                "saved": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
        )
        return {"saved": True, "count": len(self.notes)}

    def all(self) -> list:
        return list(self.notes)

    def search(self, query: str, k: int = 3) -> list:
        """TODO (Activity 2): find the notes that best match a query.

        Rules (tests/test_memory.py checks each one):
        - query_words = words(query); if it is empty, return []
        - a note's score is the number of query_words that are in words(note text + " " + note source)
        - leave out notes that score 0
        - order by score, highest first; when scores are equal, the newer note (later in self.notes) first
        - return at most k notes, as the note dicts themselves
        """
        query_words = words(query)
        if not query_words:
            return []
        scored = []
        for position, note in enumerate(self.notes):
            score = len(query_words & words(note["text"] + " " + note["source"]))
            if score > 0:
                scored.append((score, position, note))
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [note for _, _, note in scored[:k]]

    def save(self) -> None:
        if self.path:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            Path(self.path).write_text(
                json.dumps(self.notes, indent=2), encoding="utf-8"
            )


def memory_context(notebook: NoteBook, question: str, k: int = 3) -> str:
    """Notes from earlier runs that match the question, as text to add to the agent's instructions."""
    found = notebook.search(question, k)
    if not found:
        return ""
    lines = "\n".join(
        f"- {n['text']} (source: {n['source']}, saved {n['saved'][:10]})" for n in found
    )
    return (
        "\n\nNotes from earlier research that may help. They may be out of date: check anything "
        f"important again with a tool.\n{lines}"
    )
