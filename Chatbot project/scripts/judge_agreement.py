"""Compare the judge's scores with my hand labels (data/judge_labels.csv).

Run after scripts.run_judge: .venv/Scripts/python.exe -m scripts.judge_agreement
Prints how many of the labelled answers the judge agrees on, for 'correct' and for 'faithful'.
"""
import csv
import json

from app.config import ROOT
from app.eval_suite import update_summary
from app.judge import agreement

LABELS = ROOT / "data" / "judge_labels.csv"
JUDGED = ROOT / "data" / "eval_judged.csv"


def _num(value):
    return None if value in ("", "None", None) else value in ("True", "1", "1.0")


def main() -> int:
    try:
        with open(LABELS, newline="", encoding="utf-8") as f:
            labels = list(csv.DictReader(f))
        with open(JUDGED, newline="", encoding="utf-8") as f:
            scored = [{**r, "correct": _num(r["correct"]), "faithfulness": _num(r["faithfulness"])} for r in csv.DictReader(f)]
    except OSError:
        print("ERROR: labels or judged results not found. Run scripts.run_judge first.")
        return 1
    result = agreement(labels, scored)
    print(f"correct:  judge agrees on {result['correct'][0]}/{result['correct'][1]}")
    print(f"faithful: judge agrees on {result['faithful'][0]}/{result['faithful'][1]}")
    for d in result["disagreements"]:
        print(f"  DISAGREE {d['id']} {d['field']}: mine {d['mine']}, judge {d['judge']}. {d['judge_reason'][:120]}")
    update_summary({"judge": {"agreement_correct": f"{result['correct'][0]}/{result['correct'][1]}",
                              "agreement_faithful": f"{result['faithful'][0]}/{result['faithful'][1]}"}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
