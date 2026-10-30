"""Runs the whole of Day 1 in one command and prints the result.

    python -m scripts.day1_demo            # fills the app's database; refuses if it already has data
    python -m scripts.day1_demo --reset    # wipes data/ and storage/ first (fictional demo data only), then runs

It creates the demo users, turns the Cloud Support Engineer voice note into an approved, published job, applies with
all 52 CVs through the real apply page, then checks the blind records and tries a forbidden pipeline move.
Afterwards start the app (uvicorn app.main:app) and sign in as hm@example.com / recruiter@example.com
(password: demo-password-1) to look at it.
"""
import argparse
import shutil
import sys
from collections import Counter
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal, engine, init_db
from app.main import app
from app.models import Candidate, DecisionLog, Requisition, ReviewItem
from app.duplicates import duplicate_map
from app.privacy import identity_leaks, make_blind
from app.schemas import Stage
from app.supervisor import MoveRefused, move
from scripts.create_users import DEMO_PASSWORD, create_users
from scripts.upload_cvs import DEFAULT_FOLDER, upload_all

VOICE_NOTE = Path("starter_kit/voice_notes/REQ_cloud_support_engineer.wav")
SECOND_NOTE = Path("starter_kit/voice_notes/REQ_data_analyst.wav")  # stretch: a second role


def reset() -> None:
    engine.dispose()
    url = get_settings().database_url
    if url.startswith("sqlite:///"):
        try:
            Path(url.replace("sqlite:///", "", 1)).unlink(missing_ok=True)
        except PermissionError:  # Windows: another part of this process still holds the file open, so empty the tables instead of deleting the file
            from app.db import Base
            from app import models, models_ext  # noqa: F401  (registers the tables)

            Base.metadata.drop_all(engine)
    shutil.rmtree(get_settings().storage_dir, ignore_errors=True)
    print("Reset: removed the database and storage folder.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()
    if args.reset:
        reset()
    init_db()
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Requisition)):
            print("The database already has requisitions. Run again with --reset to start from an empty database.")
            return 1
        create_users(db)

    with TestClient(app, follow_redirects=False) as hm, TestClient(app, follow_redirects=False) as visitor:
        hm.post("/login", data={"email": "hm@example.com", "password": DEMO_PASSWORD})
        print("1. Hiring manager uploads the voice note ...")
        hm.post("/requisitions", data={"title": "Cloud Support Engineer"},
                files={"audio": (VOICE_NOTE.name, VOICE_NOTE.read_bytes(), "audio/wav")})
        hm.post("/requisitions/1/generate")
        print("2. Hiring manager checks the rubric and approves it, then publishes the job ...")
        hm.post("/requisitions/1/approve", data={"comment": "Day 1 demo: checked against my voice note"})
        hm.post("/requisitions/1/publish")
        print("3. Applying with every CV in the starter kit (reading PDF, Word, scans and screenshots) ...")
        accepted, refused = upload_all(visitor, 1, DEFAULT_FOLDER)
        print("4. Stretch: a second role, Data Analyst, from its own voice note ...")
        hm.post("/requisitions", data={"title": "Data Analyst"}, files={"audio": (SECOND_NOTE.name, SECOND_NOTE.read_bytes(), "audio/wav")})
        hm.post("/requisitions/2/generate")
        hm.post("/requisitions/2/approve", data={"comment": "Day 1 demo: wording checked, job text is neutral"})
        hm.post("/requisitions/2/publish")

    with SessionLocal() as db:
        req = db.get(Requisition, 1)
        items = req.rubric["items"] if req.rubric else []
        print()
        print(f"REQ-{req.id:03d} {req.status}: {len(items)} skills, weights {sum(i['weight'] for i in items)}")
        print("Must-haves: " + ", ".join(i["skill"] for i in items if i["must_have"]))
        print("Wording flags: " + ", ".join(f["phrase"] for f in (req.wording_flags or [])))
        cands = db.scalars(select(Candidate).order_by(Candidate.id)).all()
        stages = dict(Counter(c.stage for c in cands))
        unresolved = db.scalar(select(func.count()).select_from(ReviewItem).where(ReviewItem.resolved.is_(False)))
        leaks = sum(len(identity_leaks(make_blind(c), c)) for c in cands)
        print(f"Applications: {len(cands)} ({accepted} accepted, {refused} refused) stages: {stages}")
        print(f"Fields in the review queue: {unresolved} identity leaks in blind records: {leaks}")
        # The supervisor refuses a forbidden move: a candidate cannot skip screening.
        extracted = next((c for c in cands if c.stage == Stage.EXTRACTED.value), None)
        if extracted is not None:
            try:
                move(db, extracted, Stage.SHORTLISTED, "recruiter@example.com", "trying to skip screening")
            except MoveRefused as e:
                print(f"Forbidden move refused: {e}")
            db.rollback()
        names = {c.id: c.cv_name for c in cands}
        pairs = sorted({tuple(sorted((a, b))) for a, others in duplicate_map(db).items() for b in others})
        for a, b in pairs:
            print(f"Possible duplicate flagged for a person to decide: {names[a]} and {names[b]}")
        req2 = db.get(Requisition, 2)
        items2 = req2.rubric["items"] if req2 and req2.rubric else []
        if req2:
            print(f"REQ-{req2.id:03d} {req2.status}: {len(items2)} skills, weights {sum(i['weight'] for i in items2)}; "
                  f"wording flags: {', '.join(f['phrase'] for f in (req2.wording_flags or []))}")
        print(f"Decision log entries: {db.scalar(select(func.count()).select_from(DecisionLog))}")
    ok = (accepted == len(cands) and leaks == 0 and refused == 0 and req2 is not None and req2.status == "PUBLISHED")
    print("\nDay 1 demo complete." if ok else "\nDay 1 demo finished with problems: see above.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
