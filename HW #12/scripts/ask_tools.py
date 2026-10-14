"""Day 11: ask the tool-using assistant one question and see every tool call it makes.

    python -m scripts.ask_tools "Is the Finance Portal down?"
    python -m scripts.ask_tools "Close ticket INC-1017, the user says VPN works again" --show-calls
Any tool that changes data asks you to approve it here, in the terminal, first. When nobody can answer
(for example when Claude Code runs the command for you), the answer is no and nothing is changed.
"""

import argparse
import sys

from app.tool_loop import run_tool_loop


def confirm_in_terminal(summary: str) -> bool:
    print(f"\n  APPROVAL NEEDED: {summary}")
    if not sys.stdin.isatty():
        print("  (No one at a terminal to approve, for example when Claude Code runs this: treated as no.)")
        return False
    try:
        return input("  Approve? Type yes to continue: ").strip().lower() == "yes"
    except EOFError:
        # On Windows a null stdin can look like a terminal; nobody can answer, so it is no.
        print("  (No answer available: treated as no.)")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument(
        "--show-calls", action="store_true", help="print every tool call and its result"
    )
    args = ap.parse_args()
    out = run_tool_loop(args.question, confirm=confirm_in_terminal)
    for i, c in enumerate(out["calls"], 1):
        print(f"  tool call {i}: {c['name']}({c['arguments']})")
        if args.show_calls:
            result = (
                c["result"] if len(c["result"]) < 400 else c["result"][:400] + " ..."
            )
            print(f"      -> {result}")
    if not out["calls"]:
        print("  no tool calls")
    print(f"\n{out['answer']}\n")
    print(f"Model calls: {out['steps']}   Tool calls: {len(out['calls'])}")


if __name__ == "__main__":
    main()
