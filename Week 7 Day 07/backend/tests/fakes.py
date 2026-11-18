"""Scripted model replies, so no test calls a real model."""

from types import SimpleNamespace

from app.llm import says


class FakeClient:
    """Returns the given replies in order and records every request it receives."""

    def __init__(self, *replies: str):
        self.replies = list(replies)
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        return says(self.replies.pop(0))
