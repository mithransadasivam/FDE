"""Day 11, Activity 2: the schema that describes find_tickets to the model."""

from app.tools import FIND_TICKETS_SCHEMA, SEVERITIES, STATUSES, TOOLS, tool_list

PARAMS = FIND_TICKETS_SCHEMA.get("parameters", {})
PROPS = PARAMS.get("properties", {})


def test_name_and_a_description_that_says_when_to_use_it():
    assert FIND_TICKETS_SCHEMA["name"] == "find_tickets"
    description = FIND_TICKETS_SCHEMA.get("description", "")
    assert (
        len(description) >= 60
        and "ticket" in description.lower()
        and "TODO" not in description
    )


def test_status_and_severity_only_allow_real_values():
    assert PROPS["status"]["type"] == "string" and PROPS["status"]["enum"] == STATUSES
    assert (
        PROPS["severity"]["type"] == "string"
        and PROPS["severity"]["enum"] == SEVERITIES
    )


def test_application_is_a_string_and_limit_a_bounded_integer():
    assert PROPS["application"]["type"] == "string"
    assert PROPS["limit"] == {
        **PROPS["limit"],
        "type": "integer",
        "minimum": 1,
        "maximum": 20,
    }


def test_every_filter_is_optional_and_nothing_else_is_allowed():
    assert PARAMS["type"] == "object"
    assert PARAMS.get("required", []) == []
    assert PARAMS.get("additionalProperties") is False
    assert set(PROPS) == {"status", "application", "severity", "limit"}


def test_every_argument_has_a_description_and_the_model_sees_the_tool():
    assert all(p.get("description") for p in PROPS.values())
    assert {"type": "function", "function": FIND_TICKETS_SCHEMA} in tool_list(TOOLS)
