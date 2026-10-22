"""Day 18: ask the same questions as different users, and record where the answers differ.

python -m scripts.bias_test                     (5 questions x 5 profiles; CHAT_FAKE=1 works)
python -m scripts.bias_test --no-judge          (rules only: no extra model calls)

Writes logs/bias_report.json: every compared answer, its differences, and a summary per profile.
Nothing about real people: the names and profiles are invented.
"""

import argparse
import json
import os
from pathlib import Path

from app.fairness import load_profiles, load_questions, run_bias_test, summarise

OUT = "logs/bias_report.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()
    os.environ["CACHE"] = "0"
    from app import service

    profiles, questions = load_profiles(), load_questions()
    kwargs = {"judge": None} if args.no_judge else {}
    rows = run_bias_test(questions, profiles, service.answer, **kwargs)
    print(f"{'question':9} {'profile':16} differences")
    for r in rows:
        if r["differences"]:
            print(f"{r['question']:9} {r['profile']:16} {'; '.join(r['differences'])}")
            print(f"{'':26} asked: {r['asked'][:70]}")
    summary = summarise(rows)
    print("\nprofile           answers  differed  rate")
    for pid, s in summary.items():
        print(f"{pid:17} {s['answers']:7} {s['differed']:9}  {s['rate']}")
    Path(args.out).parent.mkdir(exist_ok=True)
    Path(args.out).write_text(
        json.dumps(
            {
                "fake": os.getenv("CHAT_FAKE") == "1",
                "judge": not args.no_judge,
                "summary": summary,
                "results": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nSaved {args.out}")


if __name__ == "__main__":
    main()
