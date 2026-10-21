"""Day 12, Activity 4: run the research questions, then list what went wrong in each trace.

    python -m scripts.review_runs
    python -m scripts.review_runs --questions data/my_research_questions.csv     (homework)
Every run starts with an empty notebook, so the runs can be compared fairly.
"""

import argparse
import csv

from app.agent import run_agent, save_trace
from app.memory import NoteBook
from app.trace_review import trace_problems

QUESTIONS = "data/Day12_Slide25_research_questions.csv"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=QUESTIONS)
    ap.add_argument("--max-steps", type=int, default=8)
    args = ap.parse_args()
    with open(args.questions, newline="", encoding="utf-8") as f:
        questions = [row["question"] for row in csv.DictReader(f)]
    clean = 0
    for i, q in enumerate(questions, 1):
        run = run_agent(q, notebook=NoteBook(), max_steps=args.max_steps)
        save_trace(q, run)
        tools = [a["name"] for s in run["trace"] for a in s["actions"]]
        problems = trace_problems(run)
        clean += not problems
        print(
            f"\n{i}. {q}\n   steps {len(run['trace'])}, stopped: {run['stopped']}, tools: {', '.join(tools) or 'none'}"
        )
        print("   " + run["answer"].strip().replace("\n", "\n   ")[:700])
        print("   PROBLEMS: " + ("; ".join(problems) if problems else "none found"))
    print(
        f"\nRuns with no problems found: {clean}/{len(questions)}   Traces: logs/agent_traces.jsonl"
    )


if __name__ == "__main__":
    main()
