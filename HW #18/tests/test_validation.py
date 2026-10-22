"""Day 11, Activity 3: checking the model's arguments before any tool runs."""

from app.tool_loop import run_tool, validate_arguments
from app.tools import GET_TICKET_SCHEMA, UPDATE_TICKET_SCHEMA

SCHEMA = {
    "name": "find_things",
    "parameters": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["open", "closed"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            "ratio": {"type": "number"},
            "urgent": {"type": "boolean"},
        },
        "required": ["status"],
        "additionalProperties": False,
    },
}


def test_good_arguments_have_no_problems():
    assert (
        validate_arguments(
            SCHEMA, {"status": "open", "limit": 5, "ratio": 0.5, "urgent": True}
        )
        == []
    )
    assert validate_arguments(SCHEMA, {"status": "closed", "ratio": 2}) == []


def test_not_an_object_missing_and_unknown_arguments():
    assert validate_arguments(SCHEMA, ["open"]) == ["arguments must be a JSON object"]
    assert validate_arguments(SCHEMA, {"limit": 5}) == [
        "missing required argument 'status'"
    ]
    assert validate_arguments(SCHEMA, {"status": "open", "colour": "red"}) == [
        "unknown argument 'colour'"
    ]


def test_wrong_types_including_a_bool_pretending_to_be_a_number():
    assert validate_arguments(SCHEMA, {"status": "open", "limit": "ten"}) == [
        "'limit' must be an integer"
    ]
    assert validate_arguments(SCHEMA, {"status": "open", "limit": True}) == [
        "'limit' must be an integer"
    ]
    assert validate_arguments(SCHEMA, {"status": "open", "urgent": "yes"}) == [
        "'urgent' must be a boolean"
    ]


def test_enum_and_number_limits():
    assert validate_arguments(SCHEMA, {"status": "broken"}) == [
        "'status' must be one of: open, closed"
    ]
    assert validate_arguments(SCHEMA, {"status": "open", "limit": 0}) == [
        "'limit' must be at least 1"
    ]
    assert validate_arguments(SCHEMA, {"status": "open", "limit": 500}) == [
        "'limit' must be at most 20"
    ]


def test_string_rules_and_run_tool_returns_the_problems():
    assert validate_arguments(GET_TICKET_SCHEMA, {"ticket_id": "1017"}) == [
        "'ticket_id' does not match the expected format"
    ]
    short = {"ticket_id": "INC-1017", "status": "closed", "note": "ok"}
    assert validate_arguments(UPDATE_TICKET_SCHEMA, short) == [
        "'note' must be at least 5 characters"
    ]
    assert "invalid arguments" in run_tool("get_ticket", '{"ticket_id": "1017"}')
