"""Fakes for the Day 8 tests: no test calls a real model."""

from types import SimpleNamespace


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
