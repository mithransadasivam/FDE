"""Fakes for the Day 7 tests: no test calls a real model."""

from types import SimpleNamespace

import numpy as np


class FakeChatClient:
    """Pretends to be the chat model: returns each reply in turn; the last one repeats."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=reply))]
        )


class FakeEmbedClient:
    """Stand-in for Ollama: a vector of letter counts (no real meaning, but stable)."""

    def __init__(self):
        self.embeddings = SimpleNamespace(create=self._create)

    def _create(self, model, input):
        def vec(t):
            t = t.split(": ", 1)[
                -1
            ].lower()  # drop the search_document / search_query prefix
            v = np.array([t.count(chr(97 + i)) for i in range(26)], dtype=float) + 1e-3
            return SimpleNamespace(embedding=(v / np.linalg.norm(v)).tolist())

        return SimpleNamespace(data=[vec(t) for t in input])


def chunk(id_, text="some text", source="doc.pdf", page=1, score=0.5):
    return {"id": id_, "text": text, "source": source, "page": page, "score": score}
