"""Retention (rule 10): CVs are kept for RETENTION_DAYS (180) and interview recordings for 6 months, then deleted.

Run:  python -m scripts.purge_expired            (deletes expired files and records each deletion in the decision log)
      python -m scripts.purge_expired --dry-run   (only lists what would be deleted)
Voice notes and the decision log are kept: the log records who decided what, not the personal documents themselves.
"""
import argparse
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import Candidate, DecisionLog
from app.models_ext import InterviewSession

RECORDING_DAYS = 183  # about 6 months


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


def purge(db: Session, now: datetime | None = None, dry_run: bool = False) -> dict:
    now = now or datetime.now(timezone.utc)
    s = get_settings()
    out = {"cvs_deleted": 0, "recordings_deleted": 0, "candidates": []}
    for c in db.scalars(select(Candidate)):
        applied = _aware(c.applied_at)
        if c.cv_path and applied and now - applied > timedelta(days=s.retention_days):
            p = Path(c.cv_path)
            out["candidates"].append(c.id)
            out["cvs_deleted"] += 1
            if not dry_run:
                p.unlink(missing_ok=True)
                c.cv_path = ""
                db.add(DecisionLog(actor="system", action="CV deleted after retention period", subject=f"candidate:{c.id}", reason=f"older than {s.retention_days} days"))
        sess = db.scalars(select(InterviewSession).where(InterviewSession.candidate_id == c.id)).first()
        if sess and sess.ended_at and now - _aware(sess.ended_at) > timedelta(days=RECORDING_DAYS):
            folder = s.storage_dir / "interviews" / str(c.id)
            if folder.exists():
                out["recordings_deleted"] += len(list(folder.glob("*")))
                if not dry_run:
                    shutil.rmtree(folder, ignore_errors=True)
                    db.add(DecisionLog(actor="system", action="interview recordings deleted after retention period", subject=f"candidate:{c.id}", reason="older than 6 months"))
    if not dry_run:
        db.commit()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    with SessionLocal() as db:
        r = purge(db, dry_run=args.dry_run)
    print(("Would delete" if args.dry_run else "Deleted") + f": {r['cvs_deleted']} CV(s), {r['recordings_deleted']} recording file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
