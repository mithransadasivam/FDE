"""Fakes for Day 3 tests: no test calls a real API."""

from types import SimpleNamespace

import httpx
import openai

_REQ = httpx.Request("POST", "https://example.invalid/v1/chat/completions")


class FakeClient:
    """Mimics client.chat.completions.create. Each reply is a string (returned as the
    answer) or an exception (raised). The last reply repeats."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []
        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        self.usage = usage
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        msg = SimpleNamespace(content=reply)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=self.usage)


def rate_limit():
    return openai.RateLimitError(
        "rate limited", response=httpx.Response(429, request=_REQ), body=None
    )


def timeout():
    return openai.APITimeoutError(request=_REQ)


def bad_key():
    return openai.AuthenticationError(
        "bad key", response=httpx.Response(401, request=_REQ), body=None
    )
