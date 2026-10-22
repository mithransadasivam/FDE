"""Fakes for the Day 14 tests: scripted replies for each specialist, so no test calls a real model."""

import json

from tests.day11_fakes import FakeToolClient, says

FACTS = {
    "topic": "The Finance Portal outage this morning",
    "facts": [
        {
            "text": "The Finance Portal has been down for all users since 07:58.",
            "source": "service_status",
        },
        {
            "text": "Updates are posted on the IT status page; do not raise individual tickets.",
            "source": "service_status",
        },
        {
            "text": "3 open tickets are about the Finance Portal.",
            "source": "find_tickets",
        },
    ],
    "open_questions": [],
}

NOTICE = {
    "title": "Finance Portal unavailable",
    "audience": "All staff",
    "body": "The Finance Portal has been down for everyone since 07:58. The team is working on it. "
    "Updates are posted on the IT status page.",
    "actions": [
        "Follow the IT status page for updates",
        "Do not raise a ticket for this outage",
    ],
    "sources": ["service_status", "KB-6601"],
}


def research_reply(**changes):
    return says(json.dumps({**FACTS, **changes}))


def notice_reply(**changes):
    return says(json.dumps({**NOTICE, **changes}))


def review_reply(verdict="approve", issues=()):
    return says(json.dumps({"verdict": verdict, "issues": list(issues)}))


def team_client(*replies):
    """Researcher, writer, reviewer replies in order (the researcher answers at once, without tools)."""
    return FakeToolClient(*replies)


def senders(state):
    """Who handed work back to the supervisor, in order."""
    return [h["from"] for h in state.get("handoffs", []) if h["from"] != "supervisor"]
