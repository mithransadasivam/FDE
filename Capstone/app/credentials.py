"""Credential checks (BR-20): certifications against a register, and jobs whose dates overlap.

Both are done by code from the profile read from the CV, and both only FLAG for a person: a certification that is not in the register may simply be one the register does not
know, and two jobs at the same time may be a genuine part-time or contract role. Nothing here changes a score or moves a candidate (rule 1).

The register (app/certification_register.json) is FICTIONAL, made for this project. In real use it is the issuers' own register or a verification service.
"""
import json
import re
from datetime import date
from pathlib import Path

from app.agents.document import JOB, _month

REGISTER = Path(__file__).parent / "certification_register.json"
MIN_OVERLAP_MONTHS = 2  # a month's handover between two jobs is normal; more than that is worth a question


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9+]+", " ", (s or "").lower()).strip()


def load_register() -> list[dict]:
    return json.loads(REGISTER.read_text(encoding="utf-8"))["certifications"]


def check_certifications(certs: list[str] | None) -> list[dict]:
    """Each certification named on the CV, with whether the register lists it (by name or a known short name)."""
    known = {}
    for c in load_register():
        for n in [c["name"], *c.get("aliases", [])]:
            known[_norm(n)] = c
    out = []
    for raw in certs or []:
        hit = known.get(_norm(raw))
        out.append({"certification": raw, "in_register": bool(hit), "issuer": hit["issuer"] if hit else None})
    return out


def overlapping_jobs(jobs: list[str] | None, today: date | None = None) -> list[dict]:
    """Pairs of jobs at different employers whose dates overlap by more than a month or two."""
    today = today or date.today()
    parsed = []
    for j in jobs or []:
        m = JOB.match(j.strip())
        if not m:
            continue
        try:
            parsed.append({"job": j.strip(), "company": m["company"].strip(), "start": _month(m["start"], today), "end": _month(m["end"], today)})
        except (KeyError, ValueError):
            continue
    out = []
    for i, a in enumerate(parsed):
        for b in parsed[i + 1:]:
            if a["company"].lower() == b["company"].lower():
                continue
            months = min(a["end"], b["end"]) - max(a["start"], b["start"])
            if months >= MIN_OVERLAP_MONTHS:
                out.append({"first": a["job"], "second": b["job"], "months_overlapping": months})
    return out


def credential_checks(profile: dict | None) -> dict:
    """Everything to show a person: the certifications that are not in the register and the overlapping jobs, each in a sentence."""
    p = profile or {}
    val = lambda k: (p.get(k) or {}).get("value")  # noqa: E731
    certs, overlaps = check_certifications(val("certifications")), overlapping_jobs(val("jobs"))
    items = [f"\"{c['certification']}\" is not in the certification register: please check it with the candidate." for c in certs if not c["in_register"]]
    items += [f"Two jobs overlap by {o['months_overlapping']} months: \"{o['first']}\" and \"{o['second']}\". It may be a part-time or contract role: please ask." for o in overlaps]
    return {"certifications": certs, "overlaps": overlaps, "items": items, "needs_review": bool(items)}
