"""Compares extracted fields with the answer key for 12 CVs and prints the percentage right (Prompt 11).

Run:  python -m scripts.eval_extraction            (reads the 12 CVs straight from the starter kit)
      python -m scripts.eval_extraction --db       (checks the candidates already in the database, matched by file name)
Years of experience count as right when within half a year (the key was written in a particular month).
"""
import argparse
import json
import re
from pathlib import Path

from app.agents.document import extract_profile, format_of
from app.schemas import CandidateProfile

KIT = Path("starter_kit")
KEY = KIT / "answer_keys" / "extraction_answer_key.json"
CV_DIR = KIT / "cvs" / "cloud_support_engineer"
FIELDS = ["name", "email", "phone", "current_title", "years_experience", "skills", "certifications", "education"]


def norm(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def same(field: str, got, want) -> bool:
    if field == "years_experience":
        return got is not None and abs(float(got) - float(want)) <= 0.5
    if field in ("skills", "certifications"):
        return {norm(x) for x in (got or [])} == {norm(x) for x in want}
    if field == "phone":
        return re.sub(r"\D", "", str(got or "")) == re.sub(r"\D", "", want)
    return norm(got) == norm(want)


def profile_values(profile: CandidateProfile) -> dict:
    return {f: getattr(profile, f).value for f in FIELDS}


def load_profiles(use_db: bool, key: list[dict]) -> dict[str, CandidateProfile]:
    if not use_db:
        return {k["file"]: extract_profile(CV_DIR / k["file"], format_of(CV_DIR / k["file"])) for k in key}
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Candidate

    with SessionLocal() as db:
        found = {}
        for c in db.scalars(select(Candidate).order_by(Candidate.id)):
            found[c.cv_name] = CandidateProfile.model_validate(c.profile) if c.profile else CandidateProfile()
        return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    key = json.loads(KEY.read_text(encoding="utf-8"))
    profiles = load_profiles(args.db, key)
    right = total = 0
    by_format: dict[str, list[int]] = {}
    for k in key:
        profile = profiles.get(k["file"])
        for f in FIELDS:
            total += 1
            ok = profile is not None and same(f, profile_values(profile)[f], k[f])
            right += ok
            by_format.setdefault(k["format"], [0, 0])
            by_format[k["format"]][0] += ok
            by_format[k["format"]][1] += 1
            if not ok and not args.quiet:
                got = profile_values(profile)[f] if profile else "(CV not found)"
                print(f"  WRONG {k['id']} {f}: got {got!r}, expected {k[f]!r}")
    for fmt, (r, t) in sorted(by_format.items()):
        print(f"  {fmt:11} {r}/{t}")
    pct = 100 * right / total
    print(f"Fields right: {right}/{total} = {pct:.0f}% (target: at least 90%)")
    return 0 if pct >= 90 else 1


if __name__ == "__main__":
    raise SystemExit(main())
