"""Fakes for the Day 9 tests: no test calls a real model."""

from types import SimpleNamespace


def chunk(text):
    """One streamed piece, shaped like the openai library's chunks."""
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text))])


class FakeStreamClient:
    """Pretends to be the chat model with stream=True: returns the given pieces one by one."""

    def __init__(self, *pieces):
        self.pieces = pieces
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return iter([chunk(p) for p in self.pieces])
