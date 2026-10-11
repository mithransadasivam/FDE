"""The quality gate: is the chatbot ready to ship?

Run: .venv/Scripts/python.exe -m scripts.gate
Reads the latest numbers (data/eval_summary.json, written by scripts.run_eval, scripts.run_judge, scripts.benchmark and
scripts.security_indirect) and compares each of the nine dimensions with its limits in data/eval_thresholds.json.
Prints PASS, FAIL or UNTESTED for each, then READY or NOT READY. Exits 0 only when every dimension passes, 1 otherwise.
Use --no-record to keep this run out of data/eval_history.jsonl.
"""
import argparse
from pathlib import Path

from app.gate import GateError, evaluate, load_summary, load_thresholds, record_history


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-record", action="store_true", help="do not add this run to the history")
    parser.add_argument("--summary", help="gate a saved summary file instead of data/eval_summary.json")
    parser.add_argument("--label", help="name this run in the history (default: the label in the summary)")
    args = parser.parse_args()

    try:
        thresholds = load_thresholds()
    except GateError as err:
        print(f"ERROR: {err}")
        return 1
    summary = load_summary(Path(args.summary)) if args.summary else load_summary()
    if not summary:
        print("ERROR: no evaluation numbers yet. Run scripts.run_eval first.")
        return 1

    verdict = evaluate(summary, thresholds)
    run = summary.get("run") or {}
    print(f"Gate for run '{run.get('label', '?')}' in {run.get('mode', '?')} mode\n")
    for dimension, d in verdict["dimensions"].items():
        print(f"{d['status']:<9}{d['label']}")
        for c in d["checks"]:
            shown = "no data" if c["value"] is None else c["value"]
            print(f"           {c['metric']} {shown}  (needs {c['op']} {c['limit']}){'' if c['passed'] else '  <-- not met'}")
    print(f"\n{verdict['passing']} of {verdict['total']} dimensions pass: {'READY TO SHIP' if verdict['ready'] else 'NOT READY'}")
    if not args.no_record:
        record_history(args.label or run.get("label", ""), run.get("mode", ""), verdict)
    return 0 if verdict["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
