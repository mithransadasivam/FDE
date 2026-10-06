"""Day 7 homework: check that every evidence phrase in a test set really is in its document.

    python -m scripts.check_test_set --questions data/my_retrieval_test_set.csv --folder data/my_docs
A phrase that is not in the document would make retrieval look worse than it is.
"""

import argparse
from pathlib import Path

from app.indexing import load_pages
from app.retrieval_eval import load_test_set, normalise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default="data/Day07_Slide09_retrieval_test_set.csv")
    ap.add_argument("--folder", default="data/policies")
    args = ap.parse_args()
    rows = load_test_set(args.questions)
    texts, found = {}, 0
    print(f"Checked {len(rows)} questions against {args.folder}")
    for r in rows:
        file = Path(args.folder) / r["expected_source"]
        if r["expected_source"] not in texts:
            texts[r["expected_source"]] = (
                normalise(" ".join(t for _, t in load_pages(file)))
                if file.exists()
                else None
            )
        text = texts[r["expected_source"]]
        if text is None:
            print(
                f"  FAIL  {r['question'][:60]}\n        file {r['expected_source']} not found in {args.folder}"
            )
        elif normalise(r["evidence"]) not in text:
            print(
                f'  FAIL  {r["question"][:60]}\n        evidence "{r["evidence"]}" not found in {r["expected_source"]}'
            )
        else:
            found += 1
            print(f"  OK    {r['question'][:60]}")
    print(f"\n{found} of {len(rows)} evidence phrases found.")


if __name__ == "__main__":
    main()
