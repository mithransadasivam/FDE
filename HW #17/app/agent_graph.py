"""Day 12: the same research agent, rebuilt with LangGraph.

LangGraph describes an agent as a graph: the state (here, the list of messages) flows through nodes
(functions) along edges. A conditional edge decides where to go next. A checkpointer saves the state
after every step, which gives the agent memory across turns of the same conversation (a "thread").

Done: chat_model() and langchain_tools(), which route every call through Day 11's run_tool(), so the
argument checks still apply.
Activity 3: fill in build_graph(). Check it with tests/test_agent_graph.py.
"""

import json
import os

from langchain_core.messages import SystemMessage  # noqa: F401  (you will need it)
from langchain_core.tools import StructuredTool
from langgraph.graph import END, START, MessagesState, StateGraph  # noqa: F401
from langgraph.prebuilt import (  # noqa: F401  (you will need it)
    ToolNode,
    tools_condition,
)

from app.agent import AGENT_PROMPT
from app.rag import MODEL
from app.tool_loop import run_tool


def chat_model(model: str = MODEL):
    """The course model through OpenRouter, as a LangChain chat model."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        temperature=0,
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
    )


def langchain_tools(tools: dict) -> list:
    """Day 11 / Day 12 tools as LangChain tools. Each one still goes through run_tool()."""

    def make(name, tool):
        def call(**kwargs):
            return run_tool(name, json.dumps(kwargs), {name: tool})

        return StructuredTool.from_function(
            func=call,
            name=name,
            description=tool.schema["description"],
            args_schema=tool.schema["parameters"],
        )

    return [make(name, tool) for name, tool in tools.items()]


def build_graph(
    model, tools: list, checkpointer=None, system_prompt: str = AGENT_PROMPT
):
    """TODO (Activity 3): build and compile the agent's graph.

    Rules (tests/test_agent_graph.py checks each one):
    - llm = model.bind_tools(tools)
    - a node function agent(state) that returns
          {"messages": [llm.invoke([SystemMessage(system_prompt)] + state["messages"])]}
    - graph = StateGraph(MessagesState)
    - add the node "agent" (the function) and the node "tools" (ToolNode(tools))
    - edges: START -> "agent"; from "agent" a conditional edge using tools_condition
      (it goes to "tools" when the reply has tool calls, otherwise to END); "tools" -> "agent"
    - return graph.compile(checkpointer=checkpointer)
    """
    llm = model.bind_tools(tools)

    def agent(state: MessagesState):
        return {
            "messages": [llm.invoke([SystemMessage(system_prompt)] + state["messages"])]
        }

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=checkpointer)
