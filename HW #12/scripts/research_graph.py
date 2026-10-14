"""Day 12, Activity 3: the LangGraph version of the research agent. Prints each step as it happens.

    python -m scripts.research_graph "Is the Finance Portal down?"
    python -m scripts.research_graph "Is the Finance Portal down?" --then "How many open tickets are about it?"
--then asks a follow-up in the same thread: the checkpointer gives the agent the earlier turn.
"""

import argparse

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError

from app.agent import MAX_STEPS
from app.agent_graph import build_graph, chat_model, langchain_tools
from app.memory import NoteBook
from app.research_tools import agent_tools


def ask(graph, question, config):
    print(f"\nUSER: {question}")
    try:
        for update in graph.stream(
            {"messages": [("user", question)]}, config, stream_mode="updates"
        ):
            for node, value in update.items():
                for msg in value["messages"]:
                    if node == "agent":
                        if msg.content:
                            print(f"  [agent] {str(msg.content).strip()[:300]}")
                        for call in msg.tool_calls:
                            print(f"  [agent] -> {call['name']}({call['args']})")
                    else:
                        print(f"  [tools] {msg.name}: {str(msg.content)[:110]}")
    except GraphRecursionError:
        print("  Stopped: the recursion limit was reached (the graph's step limit).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument(
        "--then", default=None, help="a follow-up question in the same thread"
    )
    ap.add_argument("--max-steps", type=int, default=MAX_STEPS)
    args = ap.parse_args()
    tools = langchain_tools(agent_tools(NoteBook()))
    graph = build_graph(chat_model(), tools, checkpointer=InMemorySaver())
    # each agent turn is two graph steps (agent, then tools), plus the final answer
    config = {
        "configurable": {"thread_id": "class-demo"},
        "recursion_limit": 2 * args.max_steps + 1,
    }
    ask(graph, args.question, config)
    if args.then:
        ask(graph, args.then, config)


if __name__ == "__main__":
    main()
