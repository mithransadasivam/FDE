"""Scans every candidate's CV for hidden or planted instructions and prints the findings (Day 3, prompt 1).

    python -m scripts.security_scan              # print what is found
    python -m scripts.security_scan --save       # also record any finding that is not already flagged (a person sees it as a red badge)

Two checks, both done by code and never by a model: text a person cannot see in a PDF (white, tiny or off the page) and sentences that look like orders to an AI
(plain or hidden in base64) in the CV text. Nothing is rejected: a finding goes to a person.
"""
import argparse
from pathlib import Path

from sqlalchemy import select

from app import security
from app.db import SessionLocal, init_db
from app.models import Candidate, DecisionLog
from app.models_ext import CvText, Flag
from app.privacy import redact_identity


def scan_candidate(db, cand: Candidate) -> list[security.Finding]:
    findings: list[security.Finding] = []
    if cand.cv_path and Path(cand.cv_path).suffix.lower() == ".pdf" and Path(cand.cv_path).exists():
        findings += security.find_hidden_text(cand.cv_path)
    raw = db.get(CvText, cand.id)
    if raw:
        findings += security.scan_for_instructions(raw.text, "the CV text") + security.scan_for_instructions(raw.pdf_metadata or "", "the PDF details")
    seen, unique = set(), []
    for f in findings:
        key = (f.kind, f.text.lower()[:80])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true", help="record findings that are not flagged yet")
    args = ap.parse_args()
    init_db()
    total, flagged_candidates = 0, 0
    with SessionLocal() as db:
        cands = db.scalars(select(Candidate).order_by(Candidate.id)).all()
        for c in cands:
            findings = scan_candidate(db, c)
            if not findings:
                continue
            flagged_candidates += 1
            print(f"\nCandidate #{c.id} ({c.cv_name})")
            for f in findings:
                total += 1
                print(f"  [{f.kind}] {f.where}{', ' + f.why if f.why else ''}: \"{f.text}\"")
                if args.save and not db.scalars(select(Flag).where(Flag.candidate_id == c.id, Flag.detail.contains(f.text[:60]))).first():
                    db.add(Flag(candidate_id=c.id, kind="hidden text in CV" if f.kind == "hidden text" else "instructions in CV ignored", detail=(redact_identity(c, f"{f.where}: {f.text}") or "")[:300]))
                    db.add(DecisionLog(actor="system", action="security scan finding", subject=f"candidate:{c.id}", reason=f"{f.kind}: {f.text[:160]}"))
        db.commit()
        print(f"\nScanned {len(cands)} candidate(s): {total} finding(s) in {flagged_candidates} CV(s). Nothing is rejected automatically: a person decides.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
