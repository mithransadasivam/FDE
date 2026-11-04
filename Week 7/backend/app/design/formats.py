"""Day 2: what each column should look like, and what personal data looks like."""

import re

FORMATS = {
    "review_id": re.compile(r"^R\d{6}$"),
    "case_id": re.compile(r"^KYC-\d{6}$"),
    "iso_date": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "year": re.compile(r"^(19|20)\d{2}$"),
    "postcode_district": re.compile(r"^[A-Z]{1,2}\d[A-Z\d]?$"),
    "int": re.compile(r"^\d+$"),
}

# Personal data that should not appear in a column unless the data dictionary says so (pii = yes)
PII_PATTERNS = {
    "phone": re.compile(r"\b07\d{3}\s?\d{6}\b"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
    "sort_code": re.compile(r"\b\d{2}-\d{2}-\d{2}\b"),
    "account_number": re.compile(r"\b\d{8}\b"),
    "full_postcode": re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s\d[A-Z]{2}\b"),
}


def matches_format(value: str, expected: str) -> bool:
    """True if value looks the way the data dictionary expects. expected is a FORMATS key,
    or 'one_of:a,b,c' for a fixed list of allowed values."""
    if expected.startswith("one_of:"):
        return value in expected.removeprefix("one_of:").split(",")
    pattern = FORMATS.get(expected)
    return bool(pattern.match(value)) if pattern else True
