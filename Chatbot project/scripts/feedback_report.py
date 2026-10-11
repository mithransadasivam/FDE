"""Print what people said about the answers (thumbs up and down), and save the thumbs down as a CSV to turn into test cases.

Run: .venv/Scripts/python.exe -m scripts.feedback_report
Reads logs/feedback.jsonl (numbers, file names and fixed reasons; the question only when the person agreed). Writes
data/thumbs_down.csv. Every row is a candidate for a new case in data/eval_suite.csv: check it, then write the case by hand.
"""
from app.config import ROOT
from app.feedback import read_feedback, summarize, to_csv


def main() -> int:
    rows = read_feedback()
    if not rows:
        print("No ratings yet. Thumbs up and down appear under each answer in the Chat tab.")
        return 0
    s = summarize(rows)
    print(f"{s['total']} ratings: {s['up']} up, {s['down']} down ({s['down_rate']:.0%})")
    for reason, n in s["by_reason"].items():
        print(f"  reason: {reason}: {n}")
    for kind, n in s["by_outcome"].items():
        print(f"  behaviour: {kind}: {n}")
    for name, n in s["files"]:
        print(f"  file most cited in a thumbs down: {name}: {n}")
    print(f"{s['with_question']} of {s['down']} thumbs down came with the question")
    (ROOT / "data" / "thumbs_down.csv").write_text(to_csv(rows), encoding="utf-8", newline="")
    print("Saved data/thumbs_down.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
