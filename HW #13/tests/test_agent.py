"""Day 12, Activity 1: the from-scratch research agent, with a fake model."""

import json

from app.agent import STOPPED_REPEAT, STOPPED_STEPS, run_agent
from app.memory import NoteBook
from app.tools import CALCULATE_SCHEMA, Tool
from tests.day12_fakes import FakeToolClient, asks, says, tool_call

TOOLS = {
    "calculate": Tool(lambda expression: {"result": eval(expression)}, CALCULATE_SCHEMA)
}


def test_an_answer_with_no_tools_is_one_step_with_its_thought():
    fake = FakeToolClient(says("Thought: I can answer directly.\nHello!"))
    run = run_agent("Hi", client=fake, tools=TOOLS)
    assert run["stopped"] == "answer" and run["answer"].endswith("Hello!")
    assert run["trace"] == [
        {"step": 1, "thought": "Thought: I can answer directly.\nHello!", "actions": []}
    ]


def test_each_step_records_its_thought_and_actions():
    fake = FakeToolClient(
        asks(tool_call("calculate", {"expression": "2 + 3"})),
        says("It is 5.\nSources: calculate"),
    )
    fake.replies[0].content = "Thought: I need the sum."
    run = run_agent("2 + 3?", client=fake, tools=TOOLS)
    assert run["trace"][0]["thought"] == "Thought: I need the sum."
    assert json.loads(run["trace"][0]["actions"][0]["result"]) == {"result": 5}
    assert len(run["trace"]) == 2 and fake.calls[1]["messages"][-1]["role"] == "tool"


def test_notes_from_earlier_runs_go_into_the_instructions():
    notebook = NoteBook()
    notebook.add("VPN-809 means the certificate expired", "KB-1101")
    fake = FakeToolClient(says("Done."))
    run_agent("What does VPN-809 mean?", client=fake, tools=TOOLS, notebook=notebook)
    system = fake.calls[0]["messages"][0]
    assert (
        system["role"] == "system"
        and "VPN-809 means the certificate expired" in system["content"]
    )
    assert fake.calls[0]["temperature"] == 0


def test_repeating_the_same_call_stops_the_run():
    same = tool_call("calculate", {"expression": "1 + 1"})
    fake = FakeToolClient(asks(same), asks(same))
    run = run_agent("Loop", client=fake, tools=TOOLS)
    assert run["stopped"] == "repeated" and run["answer"] == STOPPED_REPEAT
    assert len(run["trace"]) == 2 and run["trace"][1]["actions"] == []


def test_the_step_limit_stops_a_run_that_never_answers():
    fake = FakeToolClient(
        *[asks(tool_call("calculate", {"expression": f"{i} + 1"})) for i in range(10)]
    )
    run = run_agent("Never ends", client=fake, tools=TOOLS, max_steps=3)
    assert run["stopped"] == "step_limit" and run["answer"] == STOPPED_STEPS
    assert len(run["trace"]) == 3 and len(fake.calls) == 3
