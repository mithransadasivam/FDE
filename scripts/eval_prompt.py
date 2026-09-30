"""Score a prompt against a test set (Day 4, Activities 1 and 2, Homework Task 2).

Run from the repository root:
    python -m scripts.eval_prompt classify v1
    python -m scripts.eval_prompt classify v1 --data data/Day04_Slide05_labelled_course.csv
    python -m scripts.eval_prompt handover_note v1 --data data/handover_note_tests.csv

Reads the prompt from prompts/<name>_<version>.txt. The prompt must contain {text},
which is replaced by each row's text. Two kinds of test set, chosen by the CSV header
(or forced with --mode):
    exact      columns text,label            the reply's first word must equal the label
    checklist  columns text,expected_points  score = how many expected points the reply contains
In expected_points, separate points with ";" and give alternative wordings of one point
with "|" (e.g. "reran|re-ran;platform team"). Matching ignores case.
Every run appends one row to data/prompt_runs.csv.
"""

import argparse
import csv
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI

# Load variables (API key, optional model override) from a local .env file.
load_dotenv()
# Model to test; override by setting LLM_MODEL in .env. Defaults to Claude Haiku 4.5.
MODEL = os.getenv("LLM_MODEL", "anthropic/claude-haiku-4.5")
# CSV where every evaluation run's accuracy is recorded.
RUN_LOG = "data/prompt_runs.csv"


def get_client() -> OpenAI:
    """Build an OpenAI-compatible client that talks to OpenRouter."""
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        # Fail early with a clear message rather than a confusing API error later.
        raise RuntimeError("OPENROUTER_API_KEY is not set; add it to .env")
    # The OpenAI SDK works with OpenRouter by pointing base_url at it.
    # Retry rate-limit errors (429) with backoff: a 30-case run can exceed a new account's 20 requests/minute.
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key, max_retries=8)


def normalise(answer: str) -> str:
    """Lower-case, strip punctuation and whitespace, keep the first word."""
    # `answer or ""` guards against the model returning None.
    # Replacing "." and ":" with spaces makes "Billing." or "Label: billing" reduce to clean words.
    words = (answer or "").strip().lower().replace(".", " ").replace(":", " ").split()
    # Only the first word is compared to the label; empty answers become "".
    return words[0] if words else ""


def load_rows(path):
    """Read the labelled CSV into a list of dicts, e.g. {"text": ..., "label": ...}."""
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def split_points(cell):
    """Split an expected_points cell on ";" into a list of points, dropping blanks."""
    return [p.strip() for p in (cell or "").split(";") if p.strip()]


def point_found(point, answer):
    """True if any "|"-separated wording of the point appears in the answer (ignoring case)."""
    text = (answer or "").lower()
    return any(alt.strip().lower() in text for alt in point.split("|") if alt.strip())


def detect_mode(rows):
    """Pick the scoring kind from the CSV header: checklist if it has expected_points."""
    return "checklist" if rows and "expected_points" in rows[0] else "exact"


def evaluate(rows, template, client, model=MODEL, mode="exact"):
    """Return (accuracy, misses). Each miss is (text, expected, predicted).

    exact: accuracy is the fraction of rows whose first word equals the label.
    checklist: accuracy is points found / points expected over all rows; a row is a
    miss if any point is absent, and its "expected" holds the missing points.
    """
    if not rows:
        raise ValueError("test set is empty")
    if mode not in ("exact", "checklist"):
        raise ValueError(f"unknown mode: {mode}")
    hits, total, misses = 0, 0, []
    for row in rows:
        # Insert this row's text into the prompt template's {text} placeholder.
        prompt = template.replace("{text}", row["text"])
        # temperature=0 makes output as deterministic as possible, so runs are comparable.
        # max_tokens is small because we only need a short label back.
        r = client.chat.completions.create(
            model=model, temperature=0, max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        content = r.choices[0].message.content
        if mode == "checklist":
            # Count each expected point that appears anywhere in the answer.
            points = split_points(row["expected_points"])
            missing = [p for p in points if not point_found(p, content)]
            hits += len(points) - len(missing)
            total += len(points)
            if missing:
                misses.append((row["text"], "; ".join(missing), (content or "").strip()))
            continue
        # Clean the model's reply so it can be compared directly to the true label.
        predicted = normalise(content)
        total += 1
        if predicted == row["label"]:
            hits += 1
        else:
            # Keep wrong answers so they can be printed and inspected.
            misses.append((row["text"], row["label"], predicted))
    # Accuracy = fraction of rows (exact) or of expected points (checklist) that were right.
    return (hits / total if total else 0.0), misses


def log_run(name, version, model, accuracy, path=RUN_LOG):
    """Append one result row to the run log, so prompt versions can be compared over time."""
    # Check before opening: opening in append mode would create the file.
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            # Write the header only when the file is first created.
            w.writerow(["timestamp", "prompt", "version", "model", "accuracy"])
        w.writerow([datetime.now(timezone.utc).isoformat(), name, version, model, round(accuracy, 4)])


def main():
    # Command-line interface: prompt name, prompt version, optional data file.
    ap = argparse.ArgumentParser(description="Score a prompt against a labelled set")
    ap.add_argument("name", help="prompt name, e.g. classify")
    ap.add_argument("version", help="prompt version, e.g. v1")
    ap.add_argument("--data", default="data/labelled.csv", help="test CSV: text,label or text,expected_points")
    ap.add_argument("--mode", choices=["auto", "exact", "checklist"], default="auto",
                    help="scoring kind; auto reads it from the CSV header")
    args = ap.parse_args()

    # Load the prompt template, e.g. prompts/classify_v1.txt.
    with open(f"prompts/{args.name}_{args.version}.txt", encoding="utf-8") as f:
        template = f.read()
    rows = load_rows(args.data)
    # Run every labelled example through the model and score the answers.
    mode = detect_mode(rows) if args.mode == "auto" else args.mode
    accuracy, misses = evaluate(rows, template, get_client(), mode=mode)
    print(f"mode: {mode}")
    print(f"accuracy: {accuracy:.0%} ({len(rows) - len(misses)}/{len(rows)} cases fully right)\n")
    # Show each wrong answer (text truncated to 45 chars) to help improve the prompt.
    label = "missing" if mode == "checklist" else "expected"
    for text, expected, predicted in misses:
        print(f"MISS {text[:45]!r}  {label}={expected}  got={predicted!r}")
    log_run(args.name, args.version, MODEL, accuracy)


# Only run main() when executed as a script, not when imported.
if __name__ == "__main__":
    main()
