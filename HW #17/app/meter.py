"""Day 14: count what a run costs. Wraps the model client and records, per agent, how many calls it
made and how many tokens it used, plus the time the whole run took.

    meter = Meter(llm_client())
    meter.agent = "writer"          # each node says who is calling
    meter.chat.completions.create(...)
    meter.summary()  ->  {"calls": 7, "tokens": 18450, "seconds": 41.2, "by_agent": {...}}
"""

import time
from collections import Counter
from types import SimpleNamespace


class Meter:
    def __init__(self, client):
        self.client = client
        self.agent = "-"
        self.calls = Counter()
        self.tokens = Counter()
        self.started = time.perf_counter()
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        reply = self.client.chat.completions.create(**kwargs)
        self.calls[self.agent] += 1
        usage = getattr(reply, "usage", None)
        if usage is not None:
            self.tokens[self.agent] += (getattr(usage, "prompt_tokens", 0) or 0) + (
                getattr(usage, "completion_tokens", 0) or 0
            )
        return reply

    def summary(self) -> dict:
        return {
            "calls": sum(self.calls.values()),
            "tokens": sum(self.tokens.values()),
            "seconds": round(time.perf_counter() - self.started, 1),
            "by_agent": {
                a: {"calls": self.calls[a], "tokens": self.tokens[a]}
                for a in self.calls
            },
        }


def label(client, agent: str) -> None:
    """Tell a Meter which agent is about to call the model. Does nothing for other clients."""
    if isinstance(client, Meter):
        client.agent = agent
