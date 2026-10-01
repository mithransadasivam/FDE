"""Day 5, Activities 2 and 3: extract every invoice in a folder and report the results.

Ready to run. Claude Code runs it for you:
    python -m scripts.extract_batch            one attempt per document (Activity 2)
    python -m scripts.extract_batch --retry    with the single retry (Activity 3)
Valid results are saved as JSON in data/extracted/.
"""

import argparse
import json
from pathlib import Path

from app.extractor import extract, extract_with_retry, get_client


def main():
    # Command-line options: which folder to read, and whether to allow a retry.
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default="data/invoices")
    ap.add_argument("--retry", action="store_true", help="use extract_with_retry")
    args = ap.parse_args()

    # Pick the extraction function: one attempt (Activity 2) or with a retry (Activity 3).
    # Both are called the same way, so the loop below doesn't need to know which it is.
    run = extract_with_retry if args.retry else extract
    client = get_client()  # the OpenRouter connection; needs OPENROUTER_API_KEY in .env
    # Valid invoices are saved here as JSON files; create the folder if it is missing.
    out = Path("data/extracted")
    out.mkdir(parents=True, exist_ok=True)

    valid = 0
    # Every .txt file in the folder, in alphabetical order so runs are comparable.
    files = sorted(Path(args.folder).glob("*.txt"))
    # Table header; the numbers set the column widths so the rows line up.
    print(f"{'document':34} {'result':8} {'tries':5}  detail")
    for path in files:
        # Send the invoice text to the model. Returns (invoice or None, error or None, tries).
        obj, error, attempts = run(path.read_text(encoding="utf-8"), client)
        if obj is not None:
            # The reply passed every rule in the Invoice schema.
            valid += 1
            # Save it as <invoice name>.json; mode="json" turns dates into plain text.
            (out / f"{path.stem}.json").write_text(
                json.dumps(obj.model_dump(mode="json"), indent=2)
            )
            detail = f"total {obj.total:,.2f} {obj.currency}"
            print(f"{path.name:34} {'VALID':8} {attempts:5}  {detail}")
        else:
            # The reply broke a rule. Show only the first line of the error, cut to 70 characters.
            first_line = error.splitlines()[0][:70]
            print(f"{path.name:34} {'INVALID':8} {attempts:5}  {first_line}")
    print(f"\n{valid} of {len(files)} documents valid")


# Only run main() when the file is run as a script, not when it is imported.
if __name__ == "__main__":
    main()
