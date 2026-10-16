"""Run one request through the team and print each handoff in order. Optionally act as a person at the gate.

python -m scripts.run_team_case REQ-004 --llm offline
python -m scripts.run_team_case REQ-004 --llm offline --fault compliance=wrong      (the reviewer sends it back)
python -m scripts.run_team_case REQ-002 --llm offline --approve alex@example.com    (a person approves; one approver)
python -m scripts.run_team_case REQ-009 --llm offline --approve a@example.com --approve b@example.com   (two approvers)
python -m scripts.run_team_case REQ-001 --reply REQ-001-R1 --llm offline            (vendor reply resumes the same case)
python -m scripts.run_team_case REQ-004 --llm offline --parallel
"""
import argparse
import json
import shutil

from vendor_desk import audit, config
from vendor_desk.casedesk import make_desk
from vendor_desk.notes import case_id_for
from vendor_desk.offline_llm import OfflineLLM


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("request_id")
    ap.add_argument("--llm", choices=["live", "offline"], default=None)
    ap.add_argument("--tools", choices=["local", "mcp"], default=None)
    ap.add_argument("--reply", default=None, help="a vendor reply (e.g. REQ-001-R1) to send to the same case afterwards")
    ap.add_argument("--approve", action="append", default=[], help="a person who approves (repeat for two approvers)")
    ap.add_argument("--fault", action="append", default=[], help="offline only: role=wrong|invalid|always_invalid")
    ap.add_argument("--parallel", action="store_true")
    ap.add_argument("--keep", action="store_true", help="keep earlier runs of this case instead of starting clean")
    args = ap.parse_args()

    case_id = case_id_for(args.request_id)
    if not args.keep:
        shutil.rmtree(config.RUNS_DIR / "team" / case_id, ignore_errors=True)
    desk = make_desk(args.llm, args.tools, args.parallel)
    if args.fault and isinstance(desk.llm, OfflineLLM):
        desk.llm.faults = dict(f.split("=") for f in args.fault)
    show = lambda line: print("  " + line)   # noqa: E731
    print(f"=== {args.request_id}: handoffs in order ===")
    case = desk.submit(args.request_id, on_event=show)
    if args.reply:
        print(f"\n=== vendor reply {args.reply} ===")
        case = desk.reply(case_id, args.reply, on_event=show)
    for i, person in enumerate(args.approve, 1):
        print(f"\n=== {person} decides: approve ===")
        out = desk.act(case_id, "approve", person, "checked the evidence", on_event=show)
        print("  ->", out["message"])
        case = out["case"]
    case = desk.case(case_id)
    print(f"\n=== RESULT: {case_id} is {case['status']} ===")
    print(f"decision: {case['decision']}   flags: {case['flags']}   missing: {case['missing_items']}")
    print(f"approvers needed: {case['approvers_required']}   approved by: {[a['approver'] for a in case['approvals']]}"
          f"   vendor: {case['vendor_id']}")
    print(f"next step: {case['next_step']}")
    print(f"cost: {json.dumps(case['usage'])}")
    ok, msg = audit.verify(case_id)
    print(f"audit trail: {len(audit.read(case_id))} entries. {msg}")
    desk.close()


if __name__ == "__main__":
    main()
