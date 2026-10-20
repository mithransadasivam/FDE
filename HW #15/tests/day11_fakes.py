"""Fakes for the Day 11 tests: a pretend model that asks for tools, and a pretend database. No real calls."""

import json
import sqlite3
from types import SimpleNamespace


def tool_call(name, arguments, call_id="call_1"):
    """One tool request, shaped like the openai library's object."""
    if not isinstance(arguments, str):
        arguments = json.dumps(arguments)
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def asks(*calls):
    """A model reply that asks for one or more tools."""
    return SimpleNamespace(content="", tool_calls=list(calls))


def says(text):
    """A model reply that answers in words."""
    return SimpleNamespace(content=text, tool_calls=None)


class FakeToolClient:
    """Pretends to be the chat model: returns each scripted reply in turn; the last one repeats."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(
            {
                **kwargs,
                "messages": [
                    dict(m) if isinstance(m, dict) else m for m in kwargs["messages"]
                ],
            }
        )
        message = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def tiny_db(path):
    """A database with three tickets, for tests that must not touch data/helpdesk.db."""
    with sqlite3.connect(path) as con:
        con.execute("""CREATE TABLE tickets (id TEXT PRIMARY KEY, created TEXT, requester TEXT, application TEXT,
                       error_code TEXT, severity TEXT, status TEXT, assignee TEXT, summary TEXT, notes TEXT)""")
        con.executemany(
            "INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    "INC-0001",
                    "2026-10-01 08:00",
                    "a.user",
                    "SecureLink VPN",
                    "VPN-809",
                    "P3",
                    "open",
                    "",
                    "VPN-809",
                    "",
                ),
                (
                    "INC-0002",
                    "2026-10-02 08:00",
                    "b.user",
                    "Print Queue",
                    "PRN-310",
                    "P2",
                    "open",
                    "",
                    "Queue stuck",
                    "",
                ),
                (
                    "INC-0003",
                    "2026-10-03 08:00",
                    "c.user",
                    "SecureLink VPN",
                    "",
                    "P3",
                    "closed",
                    "",
                    "Done",
                    "",
                ),
            ],
        )
    return str(path)
