"""Day 10, Activity 4: voice notes in, tickets and illustrations out, scored against expected tickets.

    python -m scripts.voice_to_ticket
    python -m scripts.voice_to_ticket --no-images          (transcripts and tickets only)
    python -m scripts.voice_to_ticket --folder data/my_voice_notes --expected data/my_voice_tickets.csv
"""

import argparse
import csv
import time
from pathlib import Path

from app.voice import process_voice_note

FOLDER = "data/voice_notes"
EXPECTED = "data/Day10_Slide26_expected_voice_tickets.csv"
FIELDS = ["error_code", "application", "severity"]


def matches(field, got, want):
    got = (got or "").strip()
    if field == "application":
        return any(w.strip().lower() in got.lower() or got.lower() in w.strip().lower() for w in want.split("|") if w.strip())
    return got.upper() == want.strip().upper()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default=FOLDER)
    ap.add_argument("--expected", default=EXPECTED)
    ap.add_argument("--no-images", action="store_true")
    args = ap.parse_args()
    with open(args.expected, newline="", encoding="utf-8") as f:
        expected = {r["file"]: r for r in csv.DictReader(f)}
    kwargs = {"illustrator": lambda prompt: b""} if args.no_images else {}
    correct = dict.fromkeys(FIELDS, 0)
    notes = sorted(p for p in Path(args.folder).iterdir() if p.suffix.lower() in {".mp3", ".wav", ".m4a", ".ogg"})
    for path in notes:
        start = time.time()
        r = process_voice_note(path, **kwargs)
        if args.no_images and r["image"]:
            Path(r["image"]).unlink()
        print(f"\n{path.name}   ({time.time() - start:.1f} s)")
        print(f"   heard:  {r['transcript']}")
        t = r["ticket"]
        if t is None:
            print("   ticket: none")
            continue
        print(f"   ticket: {t.error_code} | {t.application} | {t.severity} | {t.summary}")
        if r["image"] and not args.no_images:
            print(f"   image:  {r['image']}")
        want = expected.get(path.name)
        if want:
            marks = []
            for field in FIELDS:
                ok = matches(field, getattr(t, field), want[field])
                correct[field] += ok
                marks.append(f"{field} {'ok' if ok else 'WRONG'}")
            print("   " + "   ".join(marks))
    print("\nCorrect fields: " + "  ".join(f"{k} {v}/{len(notes)}" for k, v in correct.items()))


if __name__ == "__main__":
    main()
