"""Deletes old interview audio (Day 2, prompt 12; rule 10: recordings are personal data kept only for the retention period).

    python -m scripts.purge_recordings            # delete audio of interviews that finished more than retention_days ago
    python -m scripts.purge_recordings --dry-run  # only say what would be deleted

Every deleted file is written to the decision log (which interview, which file, when). The written transcript on the scorecard stays; the
sound does not. (scripts/purge_expired.py is the wider sweep of CVs and whole interview folders.)
"""
import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.interview.recording import AUDIO_SUFFIXES, folder_of
from app.models import DecisionLog
from app.models_ext import InterviewSession


def _aware(dt: datetime | None) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def purge(db: Session, now: datetime | None = None, dry_run: bool = False) -> dict:
    now = now or datetime.now(timezone.utc)
    days = get_settings().retention_days
    out = {"interviews": [], "files_deleted": 0}
    for s in db.scalars(select(InterviewSession)):
        ended = _aware(s.ended_at) or _aware(s.started_at)
        if ended is None or now - ended <= timedelta(days=days):
            continue
        folder = folder_of(s)
        files = [f for f in sorted(folder.glob("*")) if f.suffix.lower() in AUDIO_SUFFIXES] if folder.exists() else []
        if not files:
            continue
        out["interviews"].append(s.id)
        for f in files:
            out["files_deleted"] += 1
            if dry_run:
                continue
            f.unlink(missing_ok=True)
            db.add(DecisionLog(actor="system", action="interview audio deleted", subject=f"interview:{s.id}",
                               reason=f"{f.name}: older than the retention period of {days} days", evidence={"file": f.name, "candidate_id": s.candidate_id}))
        if not dry_run:
            s.recording_built_at = None
    if not dry_run:
        db.commit()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    init_db()
    with SessionLocal() as db:
        r = purge(db, dry_run=args.dry_run)
    print(("Would delete" if args.dry_run else "Deleted") + f" {r['files_deleted']} audio file(s) from {len(r['interviews'])} interview(s) older than {get_settings().retention_days} days.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
