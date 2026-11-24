"""Ask the CaseFlow warehouse one question, as one person (Day 7).

    python -m scripts.ask_data "What is our backlog right now?" --user helen.achebe --layer caseflow_v2
"""

import argparse
import json

from app.data_agent import agent, service
from app.llm import llm_client


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--user", default="tom.reyes", help="tom.reyes, grace.mensah or helen.achebe")
    ap.add_argument("--layer", default="", help="a semantic layer in semantic/, for example caseflow_v2")
    a = ap.parse_args()
    ans = agent.ask(a.question, a.user, a.layer or service.current_layer(), llm_client())
    for i, att in enumerate(ans.attempts, 1):
        print(f"--- attempt {i}: {'checked' if att.check.ok else 'refused: ' + '; '.join(att.check.reasons)} {att.error}")
        print(att.sql)
    print(f"--- {ans.status} · {ans.scope}")
    if ans.assumptions:
        print("assumed:", "; ".join(ans.assumptions))
    print(json.dumps({"columns": ans.columns, "rows": ans.rows[:20]}, default=str) if ans.rows else ans.cannot_answer)


if __name__ == "__main__":
    main()
