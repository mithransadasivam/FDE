"""Day 14: run the content team on one topic. It stops when a person must decide, and saves its state,
so the decision can come later, from a new command.

python -m scripts.write_notice "The Finance Portal outage this morning"
python -m scripts.write_notice --thread <id> --decision approve  --comment "OK to send"
python -m scripts.write_notice --thread <id> --decision revise   --comment "Say when the next update is"
python -m scripts.write_notice --thread <id> --decision reject   --comment "Not needed"
python -m scripts.write_notice --thread <id> --show            (print the saved draft again)

Only a person decides. Type your own decision and comment into the command.
"""

import argparse
import sqlite3
import sys
from datetime import datetime

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from app.meter import Meter
from app.rag import llm_client
from app.team import build_team, show, slug

CHECKPOINTS = "data/team_checkpoints.db"


def print_updates(stream):
    """Print each handoff as it happens."""
    for update in stream:
        for node, change in update.items():
            if node == "__interrupt__" or not isinstance(change, dict):
                continue
            for h in change.get("handoffs", []):
                if node == "supervisor":
                    print(f"[supervisor] -> {h['to']}")
                else:
                    print(f"[{h['from']}] {h['summary']}")


def print_waiting(app, config):
    state = app.get_state(config)
    values = state.values
    if state.next == ("human",) and values.get("draft"):
        print("\n=== DRAFT FOR APPROVAL ===")
        print(show(values["draft"]))
        print("\n=== REVIEWER ===")
        print(show(values.get("review")))
        print(f"\nRevisions so far: {values.get('revisions') or 0}")
        thread = config["configurable"]["thread_id"]
        print(f"\nWaiting for a person. Thread: {thread}")
        print(
            f'Decide with: python -m scripts.write_notice --thread {thread} --decision approve|revise|reject --comment "..."'
        )
    else:
        print(f"\nStatus: {values.get('status', 'unknown')}")
        if values.get("published_to"):
            print(f"Published to {values['published_to']}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("topic", nargs="?")
    p.add_argument("--thread")
    p.add_argument("--decision", choices=["approve", "revise", "reject"])
    p.add_argument("--comment", default="")
    p.add_argument("--show", action="store_true")
    a = p.parse_args()
    if not a.topic and not a.thread:
        p.error("give a topic, or --thread with --decision or --show")
    meter = Meter(llm_client())
    with sqlite3.connect(CHECKPOINTS, check_same_thread=False) as con:
        app = build_team(meter, checkpointer=SqliteSaver(con))
        if a.topic:
            thread = f"{slug(a.topic)[:30]}-{datetime.now().astimezone():%H%M%S}"
            config = {"configurable": {"thread_id": thread}}
            print(f"Topic: {a.topic}\nThread: {thread}\n")
            print_updates(app.stream({"topic": a.topic}, config, stream_mode="updates"))
        else:
            config = {"configurable": {"thread_id": a.thread}}
            if not app.get_state(config).values:
                sys.exit(f"No saved team run with thread {a.thread}")
            if a.decision:
                print(f"You decided: {a.decision} {a.comment!r}\n")
                print_updates(
                    app.stream(
                        Command(resume={"decision": a.decision, "comment": a.comment}),
                        config,
                        stream_mode="updates",
                    )
                )
        print_waiting(app, config)
    s = meter.summary()
    if s["calls"]:
        print(
            f"\nThis command: {s['calls']} model calls, {s['tokens']} tokens, {s['seconds']} s  {s['by_agent']}"
        )


if __name__ == "__main__":
    main()
