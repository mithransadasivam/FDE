"""Day 14 homework: does the fact-checker earn its place? Runs the team without and with it on the
same topics, and compares calls, tokens, time and the automatic checks. No single agent.

python -m scripts.compare_fact_checker --topics data/my_notice_topics.csv
"""

import argparse

from app.fact_checker import build_team_with_fact_checker
from app.team import build_team
from scripts import compare_team

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--topics", default=compare_team.TOPICS)
    compare_team.main(
        p.parse_args().topics,
        teams=(("team", build_team), ("team + checker", build_team_with_fact_checker)),
        single=False,
    )
