"""Day 10, Activity 2: turn every screenshot in a folder into a ticket, and score the tickets.

    python -m scripts.triage_screenshots
    python -m scripts.triage_screenshots --max-side 768          (smaller images: homework Task 2)
    python -m scripts.triage_screenshots --folder data/my_screenshots --expected data/my_expected_tickets.csv   (homework)

The expected file has the columns file, error_code, application and severity. An application may list
several accepted names separated by |. Results are saved to data/triage_results.csv.
"""

import argparse
import csv
import time
from pathlib import Path

from PIL import Image

from app.images import resize_for_model
from app.triage import triage_screenshot
from app.vision import MIME_TYPES, estimate_image_tokens, load_image

# Where the screenshots are, and the answer key to mark them against
FOLDER = "data/screenshots"
EXPECTED = "data/Day10_Slide15_expected_tickets.csv"
# The three fields we mark as ok / WRONG
FIELDS = ("error_code", "application", "severity")


def field_ok(field, expected, got):
    """Is the model's value right? Returns True (ok) or False (WRONG)."""
    if field == "application":
        # Names are flexible: the key can list several accepted names with |,
        # and it is enough if the model's name contains one (or is part of one).
        got = (got or "").lower()
        return any(
            a.strip().lower() in got or got in a.strip().lower()
            for a in expected.split("|")
            if a.strip()
        )
    # error_code and severity must match exactly (an empty value counts as None)
    return (expected or None) == (got or None)


def run_triage(folder=FOLDER, expected_path=EXPECTED, max_side=None, quiet=False):
    """Triage every image in the folder. Returns (one row per screenshot, a summary)."""
    # Load the answer key into a dict: file name -> its expected values
    expected = {}
    if expected_path and Path(expected_path).exists():
        with open(expected_path, newline="", encoding="utf-8") as f:
            expected = {r["file"]: r for r in csv.DictReader(f)}
    rows = []
    # Go through the image files in alphabetical order (skip anything that is not an image)
    for path in sorted(
        p for p in Path(folder).iterdir() if p.suffix.lower() in MIME_TYPES
    ):
        # Get the image bytes. With --max-side, shrink the picture first (cheaper, but maybe less accurate)
        if max_side:
            data, size = resize_for_model(path, max_side)
            mime = "image/png"
        else:
            data, mime = load_image(path)
            size = Image.open(path).size
        # Ask the model for a ticket, and time how long it takes
        start = time.perf_counter()
        ticket = triage_screenshot(data, mime)
        seconds = time.perf_counter() - start
        # If the model gave no valid ticket after two tries, ticket is None and got is empty
        got = ticket.model_dump() if ticket else {}
        # One row of the results file: the image facts plus what the model said
        row = {
            "file": path.name,
            "width": size[0],
            "height": size[1],
            "tokens_estimate": estimate_image_tokens(*size),
            "seconds": round(seconds, 2),
            **{
                f"got_{k}": got.get(k)
                for k in (
                    "error_code",
                    "application",
                    "severity",
                    "summary",
                    "next_step",
                )
            },
        }
        # Mark each field against the answer key (left blank if there is no key or no ticket)
        exp = expected.get(path.name)
        for f in FIELDS:
            row[f"ok_{f}"] = field_ok(f, exp[f], got.get(f)) if exp and ticket else ""
        rows.append(row)
        # Print the screenshot's result on screen
        if not quiet:
            if ticket is None:
                print(f"FAIL  {path.name}: no valid ticket after two tries")
                continue
            # e.g. "error_code ok  application ok  severity WRONG"
            marks = "  ".join(
                f"{f} {'ok' if row[f'ok_{f}'] is True else ('WRONG' if row[f'ok_{f}'] is False else '-')}"
                for f in FIELDS
            )
            print(
                f"{path.name}\n      {ticket.error_code} | {ticket.application} | {ticket.severity} | {ticket.summary}\n      {marks}"
            )
    # Final scores: only count screenshots that were marked against a key
    scored = [r for r in rows if r["ok_severity"] != ""]
    summary = (
        {
            f: f"{sum(r[f'ok_{f}'] is True for r in scored)}/{len(scored)}"
            for f in FIELDS
        }
        if scored
        else {}
    )
    # How many screenshots produced a valid ticket
    summary["valid_tickets"] = (
        f"{sum(r['got_severity'] is not None for r in rows)}/{len(rows)}"
    )
    # Average cost (input tokens) and average time per screenshot
    summary["avg_tokens"] = (
        round(sum(r["tokens_estimate"] for r in rows) / len(rows)) if rows else 0
    )
    summary["avg_seconds"] = (
        round(sum(r["seconds"] for r in rows) / len(rows), 2) if rows else 0
    )
    return rows, summary


def main():
    # Command-line options (all optional, see the examples at the top)
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default=FOLDER)
    ap.add_argument("--expected", default=EXPECTED)
    ap.add_argument(
        "--max-side",
        type=int,
        default=None,
        help="shrink images so the longest side is at most this",
    )
    args = ap.parse_args()
    rows, summary = run_triage(args.folder, args.expected, args.max_side)
    # Save every row to a CSV file so it can be opened in a spreadsheet
    with open("data/triage_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    # Print the final score line
    print("\nCorrect fields: " + "   ".join(f"{k} {v}" for k, v in summary.items()))
    print("Full results: data/triage_results.csv")


if __name__ == "__main__":
    main()
