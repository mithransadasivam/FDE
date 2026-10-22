"""Day 14: is the team worth it? Run the content team and a single agent on the same topics, and compare
model calls, tokens, time and the automatic checks. The team runs until its draft is ready for a
person; nothing is published.

python -m scripts.compare_team                        (the three class topics)
python -m scripts.compare_team --topics data/my_topics.csv
"""

import argparse
import csv
import json
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from app.handoffs import HandoffError
from app.meter import Meter
from app.notice_checks import check_notice
from app.rag import llm_client
from app.team import build_team, single_agent_notice, slug

TOPICS = "data/Day14_Slide25_notice_topics.csv"
RESULTS = "logs/team_comparison.jsonl"


def run_team(topic, team_builder=build_team):
    meter = Meter(llm_client())
    app = team_builder(meter, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": slug(topic)}}
    app.invoke({"topic": topic}, config)
    values = app.get_state(config).values
    return (
        values.get("draft"),
        meter.summary(),
        values.get("status") or "ready for approval",
        values.get("revisions") or 0,
    )


def run_single(topic):
    meter = Meter(llm_client())
    try:
        notice, status = (
            single_agent_notice(topic, meter).model_dump(),
            "ready for approval",
        )
    except HandoffError as e:
        notice, status = None, f"stopped: {e}"
    return notice, meter.summary(), status, 0


def main(topics_file=TOPICS, teams=(("team", build_team),), single=True):
    """teams: (label, builder) pairs to compare. single: also run the single agent."""
    with open(topics_file, newline="", encoding="utf-8") as f:
        topics = list(csv.DictReader(f))
    rows = []
    for t in topics:
        must = [m.strip() for m in t["must_mention"].split(";") if m.strip()]
        runners = [
            (name, lambda x, b=builder: run_team(x, b)) for name, builder in teams
        ]
        if single:
            runners.append(("single agent", run_single))
        for version, runner in runners:
            notice, cost, status, revisions = runner(t["topic"])
            problems = check_notice(notice, must) if notice else ["no notice"]
            rows.append(
                {
                    "topic": t["topic"],
                    "version": version,
                    "status": status,
                    "revisions": revisions,
                    **{k: cost[k] for k in ("calls", "tokens", "seconds")},
                    "problems": problems,
                    "notice": notice,
                }
            )
            print(
                f"\n{t['topic']}  [{version}]  {cost['calls']} calls, {cost['tokens']} tokens, {cost['seconds']} s, revisions {revisions}"
            )
            print("  problems: " + ("; ".join(problems) if problems else "none found"))
            if notice:
                print(f"  title: {notice['title']}")
    Path(RESULTS).parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS, "a", encoding="utf-8") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)
    print(
        "\n"
        + f"{'version':14} {'calls':>6} {'tokens':>8} {'seconds':>8} {'problems':>9}"
    )
    for version in dict.fromkeys(r["version"] for r in rows):
        mine = [r for r in rows if r["version"] == version]
        print(
            f"{version:14} {sum(r['calls'] for r in mine):6} {sum(r['tokens'] for r in mine):8} "
            f"{sum(r['seconds'] for r in mine):8.1f} {sum(len(r['problems']) for r in mine):9}"
        )
    print(
        f"\nThe notices are saved in {RESULTS}. Read them: the checks cannot judge tone or truth."
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--topics", default=TOPICS)
    main(p.parse_args().topics)
