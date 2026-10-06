"""Check that every evidence phrase in the retrieval test set really is in its expected document.

Run: .venv/Scripts/python.exe -m scripts.check_evidence
"""
from app.config import DOCS_DIR
from app.retrieval_eval import check_evidence, load_retrieval_set


def main() -> int:
    try:
        rows = load_retrieval_set()
    except (OSError, ValueError) as err:
        print(f"ERROR: {err}")
        return 1
    missing = check_evidence(rows, DOCS_DIR)
    print(f"Evidence check: {len(rows) - len(missing)} of {len(rows)} found")
    for row in missing:
        print(f"  NOT FOUND ({row['problem']}): '{row['evidence']}' in {row['expected_source']}")
        print(f"    question: {row['question']}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
