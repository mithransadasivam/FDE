"""Day 14 homework: show what the fact-checker said about each draft, so a person can judge it.

python -m scripts.show_fact_checks "The Finance Portal outage this morning"
Prints the research facts, then every draft with what the checker flagged. Nothing is published.
"""

import sys

from langgraph.checkpoint.memory import InMemorySaver

from app.fact_checker import build_team_with_fact_checker
from app.meter import Meter
from app.rag import llm_client

topic = sys.argv[1]
meter = Meter(llm_client())
app = build_team_with_fact_checker(meter, checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "show"}}
n = 0
for update in app.stream({"topic": topic}, config, stream_mode="updates"):
    for node, out in update.items():
        if not isinstance(out, dict):
            continue
        if out.get("research"):
            print("RESEARCH FACTS:")
            for f in out["research"]["facts"]:
                print(f"  - [{f['source']}] {f['text']}")
        if out.get("draft"):
            n += 1
            d = out["draft"]
            print(f"\nDRAFT {n}: {d['title']}\n  {d['body']}\n  actions: {d['actions']}")
        if out.get("fact_check"):
            fc = out["fact_check"]
            print(f"  FACT-CHECK: {fc['claims_checked']} claims, unsupported: {fc['unsupported']}")
        if out.get("review"):
            print(f"  REVIEW: {out['review']}")
        if out.get("status"):
            print("  STATUS:", out["status"])
print("\ncalls/tokens:", meter.summary()["calls"], meter.summary()["tokens"])
