"""Ticket ENG-302: the bank's proof-of-address rules, as plain code.

The rules are not the model's job: they are fixed, testable and the same for every document.
The analyst sees each check and makes the decision (SC4).
"""

import calendar
import csv
import re
from datetime import date, datetime

from app import store
from app.config import ISSUERS_FILE
from app.prototype.models import Application, Check, Field

TITLES = {"mr", "mrs", "ms", "miss", "mx", "dr"}
DATE_FORMATS = ["%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%Y-%m-%d"]
DEFAULT_RULES = {"max_age_months": 3, "date_counted_from": "received_date", "ok_at": 0.85, "check_at": 0.60}


def load_rules() -> dict:
    """engagement/poa_rules.json, created with the defaults the first time. Add approved_issuers from data/."""
    rules = store.load("poa_rules.json", None)
    if rules is None:
        rules = dict(DEFAULT_RULES)
        store.save("poa_rules.json", rules)
    with open(ISSUERS_FILE, encoding="utf-8") as f:
        issuers = [r["issuer"] for r in csv.DictReader(f)]
    return {**DEFAULT_RULES, **rules, "approved_issuers": issuers}


def parse_date(text: str) -> date | None:
    """'09 Sep 2026', '9 September 2026', '09/09/2026' or '2026-09-09' -> date; anything else -> None."""
    t = re.sub(r"\s+", " ", text.strip())
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            pass
    return None


def months_before(d: date, months: int) -> date:
    """The same day `months` calendar months earlier (31 Dec minus 3 months -> 30 Sep)."""
    y, m = divmod(d.month - 1 - months, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def name_parts(name: str) -> tuple[str, str]:
    """(first name, surname), lower case, titles and punctuation removed: 'Mr J. A. Kowalski' -> ('j', 'kowalski')."""
    tokens = [t for t in re.sub(r"[^a-z' ]", " ", name.lower()).split() if t not in TITLES]
    if not tokens:
        return "", ""
    return tokens[0], tokens[-1]


def first_number(text: str) -> str:
    """The first house or flat number in an address: 'Flat 3, 14 Larkspur Row' -> '3'."""
    m = re.search(r"\d+", text)
    return m.group(0) if m else ""


def norm_postcode(text: str) -> str:
    return re.sub(r"\s", "", text).upper()


def find_postcode(text: str) -> str:
    """The UK postcode in an address, normalised: '..., GL50 3QR' -> 'GL503QR'; '' if there is none."""
    m = re.search(r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}", text.upper())
    return norm_postcode(m.group(0)) if m else ""


def check_policy(fields: dict[str, Field], app: Application, rules: dict) -> list[Check]:
    """Return four Checks, in this order: name, address, date, issuer.

    A check can only use a field whose status is "ok" or "confirmed". For any other status, the check is
    status "look" with detail f"Waiting for a person to confirm the {label in lower case}" (for example
    "Waiting for a person to confirm the statement date").

    - name ("Name matches the application"): use name_parts() on both names. pass if the surnames are
      equal and the first names are equal, or one first name is a single letter that is the first letter
      of the other. Otherwise fail, detail f"The document says {field value}; the application says {applicant_name}".
    - address ("Address matches the application"): pass if find_postcode(field value) equals
      norm_postcode(app.postcode) and first_number(field value) equals first_number(app.address_line1).
      Otherwise fail, detail f"The document shows {field value}".
    - date ("Dated within {max_age_months} months"): parse_date() the value; if None, look with detail
      "The date cannot be read as a date". The reference date is the Application attribute named by
      rules["date_counted_from"] (an ISO date). earliest = months_before(reference, rules["max_age_months"]).
      fail if the date is after app.received_date: detail "Dated after the document was received".
      fail if the date is before earliest: detail f"{(earliest - d).days} days too old (counted from the {reference name with _ as space})".
      Otherwise pass.
    - issuer ("Issuer is on the approved list"): pass if the value, compared case-insensitively, is in
      rules["approved_issuers"]. Otherwise fail, detail f"{value} is not on the approved list".

    A pass has detail "" .
    """
    def result(id_: str, label: str, ok: bool, why: str = "") -> Check:
        return Check(id=id_, label=label, status="pass" if ok else "fail", detail="" if ok else why)

    def waiting(id_: str, label: str, field: Field | None, name: str) -> Check:
        what = (field.label if field else name.replace("_", " ")).lower()
        return Check(id=id_, label=label, status="look", detail=f"Waiting for a person to confirm the {what}")

    def name_check(f: Field) -> Check:
        (first, last), (a_first, a_last) = name_parts(f.value), name_parts(app.applicant_name)
        initial = len(first) == 1 and a_first.startswith(first) or len(a_first) == 1 and first.startswith(a_first)
        ok = bool(last) and last == a_last and bool(first and a_first) and (first == a_first or initial)
        return result("name", "Name matches the application", ok,
                      f"The document says {f.value}; the application says {app.applicant_name}")

    def address_check(f: Field) -> Check:
        ok = (find_postcode(f.value) == norm_postcode(app.postcode)
              and first_number(f.value) == first_number(app.address_line1))
        return result("address", "Address matches the application", ok, f"The document shows {f.value}")

    def date_check(f: Field) -> Check:
        months = rules["max_age_months"]
        label = f"Dated within {months} months"
        written = parse_date(f.value)
        if written is None:
            return Check(id="date", label=label, status="look", detail="The date cannot be read as a date")
        counted_from = rules["date_counted_from"]
        earliest = months_before(date.fromisoformat(getattr(app, counted_from)), months)
        if written > date.fromisoformat(app.received_date):
            return result("date", label, False, "Dated after the document was received")
        return result("date", label, written >= earliest,
                      f"{(earliest - written).days} days too old (counted from the {counted_from.replace('_', ' ')})")

    def issuer_check(f: Field) -> Check:
        approved = {i.lower() for i in rules["approved_issuers"]}
        return result("issuer", "Issuer is on the approved list", f.value.strip().lower() in approved,
                      f"{f.value} is not on the approved list")

    plan = [
        ("name", "Name matches the application", "full_name", name_check),
        ("address", "Address matches the application", "address", address_check),
        ("date", f"Dated within {rules['max_age_months']} months", "statement_date", date_check),
        ("issuer", "Issuer is on the approved list", "issuer", issuer_check),
    ]
    checks = []
    for id_, label, field_name, run in plan:
        f = fields.get(field_name)
        checks.append(run(f) if f is not None and f.status in ("ok", "confirmed") else waiting(id_, label, f, field_name))
    return checks
