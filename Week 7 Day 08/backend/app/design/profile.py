"""Activity 1 (ticket ENG-201): profile the client's sample data before designing anything.

profile_column() looks at one column and says what is wrong with it. readiness() turns all the
column profiles into four scores the client can understand: complete, valid, private, labelled.
"""

import csv

from pydantic import BaseModel

from app.config import DICTIONARY_FILE, SAMPLE_FILE
from app.design.formats import PII_PATTERNS, matches_format  # noqa: F401  (you need both)


class ColumnSpec(BaseModel):
    column: str
    description: str = ""
    expected: str = ""  # a FORMATS key, "one_of:a,b,c", or "" for free text
    pii: bool = False  # the dictionary says this column holds personal data
    key: bool = False  # every value must be unique


class ColumnProfile(BaseModel):
    column: str
    rows: int
    missing_pct: float
    distinct: int
    invalid_pct: float
    bad_examples: list[str]
    pii_found: dict[str, int]
    issues: list[str]


def load_dictionary() -> dict[str, ColumnSpec]:
    with open(DICTIONARY_FILE, newline="", encoding="utf-8") as f:
        return {r["column"]: ColumnSpec(column=r["column"], description=r["description"], expected=r["expected"],
                                        pii=r["pii"] == "yes", key=r["key"] == "yes") for r in csv.DictReader(f)}


def load_sample() -> list[dict]:
    with open(SAMPLE_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def profile_column(spec: ColumnSpec, values: list) -> ColumnProfile:
    """Profile one column. A value is missing if it is None or only spaces; strip the others.

    - missing_pct: missing values as a percentage of all rows, rounded to 1 decimal
    - distinct: number of different present values
    - invalid_pct: present values that fail matches_format(value, spec.expected), as a percentage
      of present values, rounded to 1 decimal; 0 if spec.expected is empty or nothing is present
    - bad_examples: the first 3 invalid values, in order
    - pii_found: for a column whose spec.pii is False, how many present values match each
      PII_PATTERNS type, keeping only types with at least one match; {} when spec.pii is True
    - issues, in this order:
        "<missing_pct>% missing"                         when missing_pct > 5
        "<n> duplicate values"                           when spec.key and a present value repeats
                                                         (n = present values - distinct)
        "<invalid_pct>% not in the expected format"      when invalid_pct > 2
        "undeclared personal data: phone (3), email (1)" when pii_found is not empty, types in
                                                         PII_PATTERNS order
    """
    present = [str(v).strip() for v in values if v is not None and str(v).strip()]
    rows = len(values)
    missing_pct = round(100 * (rows - len(present)) / rows, 1) if rows else 0.0
    distinct = len(set(present))
    bad = [v for v in present if spec.expected and not matches_format(v, spec.expected)]
    invalid_pct = round(100 * len(bad) / len(present), 1) if present and spec.expected else 0.0
    pii_found: dict[str, int] = {}
    if not spec.pii:
        for name, rx in PII_PATTERNS.items():
            n = sum(1 for v in present if rx.search(v))
            if n:
                pii_found[name] = n
    issues = []
    if missing_pct > 5:
        issues.append(f"{missing_pct:g}% missing")
    if spec.key and len(present) - distinct > 0:
        issues.append(f"{len(present) - distinct} duplicate values")
    if invalid_pct > 2:
        issues.append(f"{invalid_pct:g}% not in the expected format")
    if pii_found:
        issues.append("undeclared personal data: " + ", ".join(f"{k} ({v})" for k, v in pii_found.items()))
    return ColumnProfile(column=spec.column, rows=rows, missing_pct=missing_pct, distinct=distinct,
                         invalid_pct=invalid_pct, bad_examples=bad[:3], pii_found=pii_found, issues=issues)


def status(pct: float) -> str:
    return "green" if pct <= 2 else "amber" if pct <= 10 else "red"


REQUIRED = ["review_id", "doc_type", "doc_date", "received_date", "file_format", "decision"]


def readiness(rows: list[dict], profiles: list[ColumnProfile]) -> list[dict]:
    """Four readiness scores for the client, each green, amber or red."""
    by = {p.column: p for p in profiles}
    worst_missing = max(by[c].missing_pct for c in REQUIRED)
    worst_invalid = max(p.invalid_pct for p in profiles)
    pii_rows = sum(sum(p.pii_found.values()) for p in profiles)
    asked = [r for r in rows if r["decision"] != "approved"]
    unlabelled = sum(1 for r in asked if not r["reason_code"].strip())
    unlabelled_pct = round(100 * unlabelled / len(asked), 1) if asked else 0.0
    return [
        {"name": "Complete", "status": status(worst_missing), "value": f"{worst_missing:g}%",
         "detail": "worst missing rate in a required column"},
        {"name": "Valid", "status": status(worst_invalid), "value": f"{worst_invalid:g}%",
         "detail": "worst rate of values in the wrong format"},
        {"name": "Private", "status": "green" if pii_rows == 0 else "red", "value": str(pii_rows),
         "detail": "values with personal data the export should not contain"},
        {"name": "Labelled", "status": status(unlabelled_pct), "value": f"{unlabelled_pct:g}%",
         "detail": "asks and escalations with no reason code"},
    ]
