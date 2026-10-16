"""Day 12, Activity 3: the agent as a LangGraph graph, with a fake chat model."""

import pytest
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError

from app.agent_graph import build_graph, langchain_tools
from app.tools import CALCULATE_SCHEMA, Tool
from tests.day12_fakes import FakeGraphModel, graph_asks, graph_says

TOOLS = langchain_tools(
    {
        "calculate": Tool(
            lambda expression: {"result": eval(expression)}, CALCULATE_SCHEMA
        )
    }
)


def model(*replies):
    return FakeGraphModel(replies=list(replies), seen=[], bound=[])


def test_the_graph_has_an_agent_node_and_a_tools_node():
    graph = build_graph(model(graph_says("Hi")), TOOLS)
    assert {"agent", "tools"} <= set(graph.get_graph().nodes)


def test_no_tool_call_goes_straight_to_the_end():
    m = model(graph_says("Hello!"))
    out = build_graph(m, TOOLS).invoke({"messages": [("user", "Hi")]})
    assert [type(x).__name__ for x in out["messages"]] == ["HumanMessage", "AIMessage"]
    assert m.bound == ["calculate"]


def test_a_tool_call_runs_and_goes_back_to_the_agent_with_the_system_prompt():
    m = model(graph_asks("calculate", {"expression": "2 + 3"}), graph_says("It is 5."))
    out = build_graph(m, TOOLS, system_prompt="Be brief.").invoke(
        {"messages": [("user", "2 + 3?")]}
    )
    assert (
        isinstance(out["messages"][2], ToolMessage)
        and '"result": 5' in out["messages"][2].content
    )
    assert out["messages"][-1].content == "It is 5."
    assert (
        isinstance(m.seen[1][0], SystemMessage) and m.seen[1][0].content == "Be brief."
    )


def test_the_checkpointer_remembers_earlier_turns_of_the_same_thread():
    m = model(graph_says("Noted."), graph_says("You asked about VPN-809."))
    graph = build_graph(m, TOOLS, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "t1"}}
    graph.invoke({"messages": [("user", "Remember VPN-809.")]}, config)
    out = graph.invoke({"messages": [("user", "What did I ask about?")]}, config)
    assert len(out["messages"]) == 4 and "Remember VPN-809." in [
        x.content for x in m.seen[1]
    ]


def test_the_recursion_limit_stops_a_graph_that_never_answers():
    m = model(
        *[
            graph_asks("calculate", {"expression": f"{i} + 1"}, f"c{i}")
            for i in range(20)
        ]
    )
    with pytest.raises(GraphRecursionError):
        build_graph(m, TOOLS).invoke(
            {"messages": [("user", "Loop")]}, {"recursion_limit": 5}
        )
    assert (
        len(m.seen) <= 3
    )  # the limit counts graph steps: agent and tools nodes both count
