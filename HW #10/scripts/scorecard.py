"""Day 8, Activity 4: print an eight-dimension scorecard for the chatbot.

    python -m scripts.quality_gate          (first: writes data/quality_report.json)
    python -m scripts.scorecard              (asks 8 probe questions, about 30 seconds)
    python -m scripts.scorecard --name my_docs --thresholds data/my_quality_thresholds.json   (homework)

Saves the scorecard, with every probe answer, to data/scorecard.json.
"""

import argparse
import json
from pathlib import Path

from app.advanced import MODES, RAG_MODE, retrieve
from app.rag import answer
from app.scorecard import FAIL, UNTESTED, build_scorecard, run_probes

REPORT = "data/quality_report.json"
THRESHOLDS = "data/Day08_Slide37_quality_thresholds.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default=RAG_MODE, choices=MODES)
    ap.add_argument("--name", default="it_policies", help="collection name")
    ap.add_argument("--report", default=REPORT)
    ap.add_argument("--thresholds", default=THRESHOLDS)
    args = ap.parse_args()

    report = (
        json.loads(Path(args.report).read_text(encoding="utf-8"))
        if Path(args.report).exists()
        else {}
    )
    thresholds = json.loads(Path(args.thresholds).read_text(encoding="utf-8"))
    if report and report.get("mode") != args.mode:
        print(
            f"Note: {args.report} is from mode {report.get('mode')}; the probes use mode {args.mode}.\n"
        )

    def ask(question, previous):
        r = retrieve(question, mode=args.mode, previous=previous, name=args.name)
        return answer(r["query"], retrieve=lambda _: r["chunks"])

    print(f"Mode: {args.mode}   asking 8 probe questions ...")
    probes = run_probes(ask)
    card = build_scorecard(report.get("summary"), thresholds, probes)

    print()
    for p in probes:
        shown = p["error"] or p["answer"].replace("\n", " ")
        print(f"  {p['kind']:20} {repr(p['question'])[:44]:44} -> {shown[:70]}")
    print(f"\n  {'Dimension':12} {'Verdict':9} Evidence")
    for row in card:
        print(f"  {row['dimension']:12} {row['verdict']:9} {row['evidence']}")
    weak = [r["dimension"] for r in card if r["verdict"] in (FAIL, UNTESTED)]
    print(
        f"\nPassed {8 - len(weak)} of 8.   Fail or untested: {', '.join(weak) if weak else 'none'}"
    )
    Path("data/scorecard.json").write_text(
        json.dumps({"mode": args.mode, "scorecard": card, "probes": probes}, indent=2),
        encoding="utf-8",
    )
    print("Saved: data/scorecard.json")


if __name__ == "__main__":
    main()
