"""Day 11, Activity 1: the tool-calling loop, with a fake model."""

import json

from app.tool_loop import STOPPED, run_tool_loop
from app.tools import CALCULATE_SCHEMA, Tool
from tests.day11_fakes import FakeToolClient, asks, says, tool_call

TOOLS = {
    "calculate": Tool(lambda expression: {"result": eval(expression)}, CALCULATE_SCHEMA)
}


def test_no_tool_needed_means_one_model_call():
    fake = FakeToolClient(says("Hello! I can check tickets and services."))
    out = run_tool_loop("Hello", client=fake, tools=TOOLS)
    assert out == {
        "answer": "Hello! I can check tickets and services.",
        "calls": [],
        "steps": 1,
    }
    assert fake.calls[0]["temperature"] == 0
    assert fake.calls[0]["tools"][0]["function"]["name"] == "calculate"


def test_the_tool_result_goes_back_to_the_model():
    fake = FakeToolClient(
        asks(tool_call("calculate", {"expression": "2 + 3"})), says("It is 5.")
    )
    out = run_tool_loop("What is 2 + 3?", client=fake, tools=TOOLS)
    assert out["answer"] == "It is 5." and out["steps"] == 2
    second = fake.calls[1]["messages"]
    assert second[0]["role"] == "system" and second[1] == {
        "role": "user",
        "content": "What is 2 + 3?",
    }
    assert (
        second[2]["role"] == "assistant"
        and second[2]["tool_calls"][0]["id"] == "call_1"
    )
    assert second[3]["role"] == "tool" and second[3]["tool_call_id"] == "call_1"
    assert json.loads(second[3]["content"]) == {"result": 5}


def test_several_calls_in_one_reply_are_all_answered_in_order():
    fake = FakeToolClient(
        asks(
            tool_call("calculate", {"expression": "1 + 1"}, "a"),
            tool_call("calculate", {"expression": "2 * 5"}, "b"),
        ),
        says("2 and 10."),
    )
    out = run_tool_loop("Two sums", client=fake, tools=TOOLS)
    assert [c["arguments"] for c in out["calls"]] == [
        '{"expression": "1 + 1"}',
        '{"expression": "2 * 5"}',
    ]
    assert [
        m["tool_call_id"] for m in fake.calls[1]["messages"] if m["role"] == "tool"
    ] == ["a", "b"]


def test_a_tool_error_is_sent_back_not_raised():
    fake = FakeToolClient(
        asks(tool_call("no_such_tool", {})), says("Sorry, I could not do that.")
    )
    out = run_tool_loop("Do something", client=fake, tools=TOOLS)
    assert "unknown tool" in out["calls"][0]["result"]
    assert out["answer"] == "Sorry, I could not do that."


def test_the_loop_stops_after_max_steps():
    fake = FakeToolClient(
        asks(tool_call("calculate", {"expression": "1"}))
    )  # asks for tools forever
    out = run_tool_loop("Loop", client=fake, tools=TOOLS, max_steps=3)
    assert out["answer"] == STOPPED and out["steps"] == 3
    assert len(fake.calls) == 3 and len(out["calls"]) == 3
