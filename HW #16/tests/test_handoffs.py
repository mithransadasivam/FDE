"""Activity 1: parse_handoff() checks what one agent passes to the next. Run: pytest tests/test_handoffs.py"""

import json

import pytest

from app.handoffs import (
    HandoffError,
    Notice,
    ResearchNotes,
    Review,
    ask_for,
    parse_handoff,
)
from tests.day14_fakes import FACTS, NOTICE, FakeToolClient, says


def test_plain_json_becomes_a_checked_object():
    notes = parse_handoff(json.dumps(FACTS), ResearchNotes)
    assert isinstance(notes, ResearchNotes)
    assert notes.facts[0].source == "service_status"


def test_fences_and_words_around_the_json_are_ignored():
    text = "Here is the notice:\n```json\n" + json.dumps(NOTICE) + "\n```\nLet me know!"
    assert parse_handoff(text, Notice).title == "Finance Portal unavailable"


@pytest.mark.parametrize(
    "text, message",
    [
        ("I could not find anything.", "no JSON object found"),
        ('{"verdict": "approve", }', "not valid JSON: "),
        (
            '{"verdict": "maybe"}',
            "does not match Review: verdict: Input should be 'approve' or 'revise'",
        ),
    ],
)
def test_bad_replies_raise_a_handoff_error_that_says_why(text, message):
    with pytest.raises(HandoffError) as e:
        parse_handoff(text, Review)
    assert str(e.value).startswith(message)


def test_the_error_names_the_field_paths_at_most_three():
    bad = {
        "topic": "x",
        "facts": [{"text": "A fact with no source."}, {"source": "s"}, {}],
    }
    with pytest.raises(HandoffError) as e:
        parse_handoff(json.dumps(bad), ResearchNotes)
    message = str(e.value)
    assert message.startswith(
        "does not match ResearchNotes: facts.0.source: Field required; "
    )
    assert message.count(";") == 2


def test_ask_for_retries_once_with_the_error_then_succeeds():
    client = FakeToolClient(
        says("Sure! The verdict is approve."), says('{"verdict": "approve"}')
    )
    result = ask_for(client, "m", "You review.", "Check this.", Review)
    assert result.verdict == "approve"
    retry = client.calls[1]["messages"][-1]["content"]
    assert retry.startswith("That reply could not be used: no JSON object found")
