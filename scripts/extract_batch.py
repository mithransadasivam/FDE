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
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default="data/invoices")
    ap.add_argument("--retry", action="store_true", help="use extract_with_retry")
    args = ap.parse_args()

    run = extract_with_retry if args.retry else extract
    client = get_client()
    out = Path("data/extracted")
    out.mkdir(parents=True, exist_ok=True)

    valid = 0
    files = sorted(Path(args.folder).glob("*.txt"))
    print(f"{'document':34} {'result':8} {'tries':5}  detail")
    for path in files:
        obj, error, attempts = run(path.read_text(encoding="utf-8"), client)
        if obj is not None:
            valid += 1
            (out / f"{path.stem}.json").write_text(
                json.dumps(obj.model_dump(mode="json"), indent=2)
            )
            detail = f"total {obj.total:,.2f} {obj.currency}"
            print(f"{path.name:34} {'VALID':8} {attempts:5}  {detail}")
        else:
            first_line = error.splitlines()[0][:70]
            print(f"{path.name:34} {'INVALID':8} {attempts:5}  {first_line}")
    print(f"\n{valid} of {len(files)} documents valid")


if __name__ == "__main__":
    main()
