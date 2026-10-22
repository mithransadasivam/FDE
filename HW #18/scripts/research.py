"""Day 12: ask the from-scratch research agent a question and print every step it takes.

    python -m scripts.research "What causes VPN-809, and how many VPN tickets are open?"
    python -m scripts.research "..." --max-steps 4          (a tighter step limit)
    python -m scripts.research "..." --no-memory            (start with an empty notebook; save nothing)
Notes are kept in data/agent_notes.json between runs. Every run is added to logs/agent_traces.jsonl.
"""

import argparse

from app.agent import MAX_STEPS, print_trace, run_agent, save_trace
from app.memory import NoteBook

NOTES = "data/agent_notes.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--max-steps", type=int, default=MAX_STEPS)
    ap.add_argument("--no-memory", action="store_true")
    args = ap.parse_args()
    notebook = NoteBook(None if args.no_memory else NOTES)
    before = len(notebook.all())
    recalled = notebook.search(args.question, 3)
    if recalled:
        print(f"Recalled from memory ({len(recalled)} notes from earlier runs):")
        for n in recalled:
            print(f"  - {n['text']} (source: {n['source']})")
    run = run_agent(args.question, notebook=notebook, max_steps=args.max_steps)
    print_trace(run)
    print(f"\nANSWER\n{run['answer']}\n")
    notebook.save()
    if not args.no_memory:
        print(f"Notes: {before} before, {len(notebook.all())} now ({NOTES})")
    save_trace(args.question, run)


if __name__ == "__main__":
    main()
