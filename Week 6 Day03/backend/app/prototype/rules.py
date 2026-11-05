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
    def usable(name: str) -> Field | None:
        f = fields.get(name)
        return f if f is not None and f.status in ("ok", "confirmed") else None

    def look(id_: str, label: str, name: str) -> Check:
        what = fields[name].label.lower() if name in fields else name.replace("_", " ")
        return Check(id=id_, label=label, status="look", detail=f"Waiting for a person to confirm the {what}")

    checks: list[Check] = []

    # name
    label = "Name matches the application"
    f = usable("full_name")
    if f is None:
        checks.append(look("name", label, "full_name"))
    else:
        (f1, s1), (f2, s2) = name_parts(f.value), name_parts(app.applicant_name)
        first_ok = f1 == f2 or (bool(f1) and bool(f2) and ((len(f1) == 1 and f2.startswith(f1)) or (len(f2) == 1 and f1.startswith(f2))))
        ok = bool(s1) and s1 == s2 and first_ok
        checks.append(Check(id="name", label=label, status="pass" if ok else "fail",
                            detail="" if ok else f"The document says {f.value}; the application says {app.applicant_name}"))

    # address
    label = "Address matches the application"
    f = usable("address")
    if f is None:
        checks.append(look("address", label, "address"))
    else:
        ok = (find_postcode(f.value) == norm_postcode(app.postcode)
              and first_number(f.value) == first_number(app.address_line1))
        checks.append(Check(id="address", label=label, status="pass" if ok else "fail",
                            detail="" if ok else f"The document shows {f.value}"))

    # date
    months = rules["max_age_months"]
    label = f"Dated within {months} months"
    f = usable("statement_date")
    if f is None:
        checks.append(look("date", label, "statement_date"))
    else:
        d = parse_date(f.value)
        if d is None:
            checks.append(Check(id="date", label=label, status="look", detail="The date cannot be read as a date"))
        else:
            ref_name = rules["date_counted_from"]
            reference = date.fromisoformat(getattr(app, ref_name))
            earliest = months_before(reference, months)
            if d > date.fromisoformat(app.received_date):
                checks.append(Check(id="date", label=label, status="fail", detail="Dated after the document was received"))
            elif d < earliest:
                checks.append(Check(id="date", label=label, status="fail",
                                    detail=f"{(earliest - d).days} days too old (counted from the {ref_name.replace('_', ' ')})"))
            else:
                checks.append(Check(id="date", label=label, status="pass", detail=""))

    # issuer
    label = "Issuer is on the approved list"
    f = usable("issuer")
    if f is None:
        checks.append(look("issuer", label, "issuer"))
    else:
        approved = {i.lower() for i in rules["approved_issuers"]}
        ok = f.value.strip().lower() in approved
        checks.append(Check(id="issuer", label=label, status="pass" if ok else "fail",
                            detail="" if ok else f"{f.value} is not on the approved list"))
    return checks

