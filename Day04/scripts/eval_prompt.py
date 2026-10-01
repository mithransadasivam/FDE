"""Score a prompt against a labelled set (Day 4, Activities 1 and 2).

Run from the repository root:
    python -m scripts.eval_prompt classify v1
    python -m scripts.eval_prompt classify v1 --data data/Day04_Slide05_labelled_course.csv

Reads the prompt from prompts/<name>_<version>.txt. The prompt must contain {text},
which is replaced by each row's text. The labelled set is a CSV with columns text,label.
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
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)


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


def evaluate(rows, template, client, model=MODEL):
    """Return (accuracy, misses). Each miss is (text, expected, predicted)."""
    hits, misses = 0, []
    for row in rows:
        # Insert this row's text into the prompt template's {text} placeholder.
        prompt = template.replace("{text}", row["text"])
        # temperature=0 makes output as deterministic as possible, so runs are comparable.
        # max_tokens is small because we only need a short label back.
        r = client.chat.completions.create(
            model=model, temperature=0, max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        # Clean the model's reply so it can be compared directly to the true label.
        predicted = normalise(r.choices[0].message.content)
        if predicted == row["label"]:
            hits += 1
        else:
            # Keep wrong answers so they can be printed and inspected.
            misses.append((row["text"], row["label"], predicted))
    # Accuracy = fraction of rows the model labelled correctly.
    return hits / len(rows), misses


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
    ap.add_argument("--data", default="data/labelled.csv", help="labelled CSV with columns text,label")
    args = ap.parse_args()

    # Load the prompt template, e.g. prompts/classify_v1.txt.
    with open(f"prompts/{args.name}_{args.version}.txt", encoding="utf-8") as f:
        template = f.read()
    rows = load_rows(args.data)
    # Run every labelled example through the model and score the answers.
    accuracy, misses = evaluate(rows, template, get_client())
    print(f"accuracy: {accuracy:.0%} ({len(rows) - len(misses)}/{len(rows)})\n")
    # Show each wrong answer (text truncated to 45 chars) to help improve the prompt.
    for text, expected, predicted in misses:
        print(f'MISS "{text[:45]}"  expected={expected}  got={predicted}')
    log_run(args.name, args.version, MODEL, accuracy)


# Only run main() when executed as a script, not when imported.
if __name__ == "__main__":
    main()
