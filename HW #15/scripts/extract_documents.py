"""Day 10 homework, Task 1: extract fields from every asset label image and score them.

    python -m scripts.extract_documents
    python -m scripts.extract_documents --folder data/asset_labels --expected data/Day10_HW_Slide03_expected_asset_labels.csv

The expected file has the columns file, asset_tag, device_type, serial_number and purchase_date.
Results are saved to data/extract_results.csv.
"""

import argparse
import csv
from pathlib import Path

from app.extract_assets import extract_asset
from app.vision import MIME_TYPES, load_image

FOLDER = "data/asset_labels"
EXPECTED = "data/Day10_HW_Slide03_expected_asset_labels.csv"
FIELDS = ("asset_tag", "device_type", "serial_number", "purchase_date")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default=FOLDER)
    ap.add_argument("--expected", default=EXPECTED)
    args = ap.parse_args()
    with open(args.expected, newline="", encoding="utf-8") as f:
        expected = {r["file"]: r for r in csv.DictReader(f)}
    rows = []
    for path in sorted(p for p in Path(args.folder).iterdir() if p.suffix.lower() in MIME_TYPES):
        data, mime = load_image(path)
        asset = extract_asset(data, mime)
        got = {k: (str(v) if v is not None else "") for k, v in asset.model_dump().items()} if asset else {}
        exp = expected.get(path.name)
        row = {"file": path.name, **{f"got_{k}": got.get(k, "") for k in (*FIELDS, "model", "department")}}
        for field in FIELDS:
            row[f"ok_{field}"] = (got.get(field) == exp[field]) if exp and asset else ""
        rows.append(row)
        if asset is None:
            print(f"FAIL  {path.name}: no valid label after two tries")
            continue
        marks = "  ".join(
            f"{f} {'ok' if row[f'ok_{f}'] is True else ('WRONG' if row[f'ok_{f}'] is False else '-')}"
            for f in FIELDS
        )
        print(
            f"{path.name}\n      {got['asset_tag']} | {got['device_type']} | {got['model']} | "
            f"{got['serial_number']} | {got['purchase_date']} | {got['department']}\n      {marks}"
        )
        for field in FIELDS:
            if row[f"ok_{field}"] is False:
                print(f"      WRONG {field}: expected {exp[field]!r}, got {got[field]!r}")
    scored = [r for r in rows if r[f"ok_{FIELDS[0]}"] != ""]
    print(
        "\nCorrect fields: "
        + "   ".join(f"{f} {sum(r[f'ok_{f}'] is True for r in scored)}/{len(scored)}" for f in FIELDS)
    )
    with open("data/extract_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("Full results: data/extract_results.csv")


if __name__ == "__main__":
    main()
