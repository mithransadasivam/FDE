"""Run the single planning agent on one request file and print the trace and the assessment.

python -m scripts.run_case REQ-007                      (uses LLM_MODE, default: the hosted model)
python -m scripts.run_case REQ-007 --llm offline
python -m scripts.run_case REQ-001-R1 --llm offline     (a vendor reply: continues the notes of case VOB-001)
"""
import argparse
import json

from vendor_desk import config
from vendor_desk.agent import run_agent
from vendor_desk.backends import make_backend
from vendor_desk.followup import draft_followup
from vendor_desk.llm import make_llm
from vendor_desk.notes import case_id_for, load_notes, save_trace, update_notes
from vendor_desk.review import review_run


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("request_id")
    ap.add_argument("--llm", choices=["live", "offline"], default=None)
    ap.add_argument("--tools", choices=["local", "mcp"], default=None)
    ap.add_argument("--engine", default="part1")
    args = ap.parse_args()

    case_id = case_id_for(args.request_id)
    notes = load_notes(args.engine, case_id) if "-R" in args.request_id else None
    run = run_agent(args.request_id, make_llm(args.llm), make_backend(args.tools), notes=notes, case_id=case_id)
    save_trace(args.engine, case_id, run)
    problems = review_run(run, notes)
    draft = draft_followup(run.assessment, "requester", args.request_id) if run.assessment else None
    update_notes(args.engine, case_id, run, notes=notes, draft=draft)

    print(f"=== TRACE {args.request_id} (case {case_id}, step limit {config.STEP_LIMIT}) ===")
    for e in run.trace:
        detail = {k: v for k, v in e.items() if k not in ("step", "at", "type")}
        print(f"[{e['step']}] {e['type']:<14} {json.dumps(detail, ensure_ascii=False)[:230]}")
    print(f"\nstatus: {run.status}   model calls: {run.usage.calls}   tool calls: {run.usage.tool_calls}   "
          f"tokens: {run.usage.tokens}")
    print("\n=== ASSESSMENT ===")
    print(json.dumps(run.assessment, indent=2, ensure_ascii=False) if run.assessment else "(none: " + run.message + ")")
    if draft:
        print("\n=== DRAFT FOLLOW-UP (not sent) ===\n" + draft["body"])
    print("\n=== TRACE REVIEW ===")
    print("clean" if not problems else "\n".join(f"- {p['severity']}: {p['code']}: {p['detail']}" for p in problems))


if __name__ == "__main__":
    main()
