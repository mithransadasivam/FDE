"""Checks that an architecture decision record has what a reviewer needs (done, not a ticket)."""

import re

SECTIONS = ["Context", "Options considered", "Decision", "Consequences"]


def check_adr(md: str) -> list[dict]:
    heads = {h.strip().lower() for h in re.findall(r"^##\s+(.+)$", md, flags=re.M)}
    checks = [{"check": f"Has a “{s}” section", "ok": s.lower() in heads} for s in SECTIONS]
    checks.append({"check": "States a status", "ok": bool(re.search(r"\*\*Status:\*\*\s*(proposed|accepted|superseded)", md, re.I))})
    checks.append({"check": "Compares all three options", "ok": all(re.search(rf"Option {x}\b", md) for x in "ABC")})
    checks.append({"check": "Quotes a run-cost in GBP", "ok": bool(re.search(r"£\s?\d", md))})
    checks.append({"check": "Names a client rule", "ok": bool(re.search(r"UK|person (makes|decides)|read-only|audit", md, re.I))})
    checks.append({"check": "No placeholders left", "ok": "<" not in re.sub(r"<!--.*?-->", "", md, flags=re.S)})
    return checks
