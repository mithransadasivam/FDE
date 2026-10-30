"""Deletes old interview audio (Day 2, prompt 12; rule 10: recordings are personal data kept only for the retention period).

    python -m scripts.purge_recordings            # delete audio of interviews that finished more than retention_days ago
    python -m scripts.purge_recordings --dry-run  # only say what would be deleted

Every deletion is written to the decision log (what, which interview, when). After the retention period it removes the SOUND, the written TRANSCRIPT (and the quotes
taken from it) and the CV FILE; levels, decisions and who made them stay, so the audit trail does. (scripts/purge_expired.py is the older sweep of whole folders.)

Run it every night. On Windows: Task Scheduler, a daily task running  python -m scripts.purge_recordings  in the project folder. On Linux or in Docker: a cron line,
for example  15 3 * * *  cd /app && python -m scripts.purge_recordings  (3:15 every night).
"""
import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.interview.recording import AUDIO_SUFFIXES, folder_of
from app.models import Candidate, DecisionLog
from app.models_ext import CvText, HumanInterview, InterviewSession


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
        _clear_transcripts(db, s, out, dry_run)
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
    _purge_cv_files(db, now, days, out, dry_run)
    if not dry_run:
        db.commit()
    return out


GONE = "[deleted after the retention period]"


def _clear_transcripts(db: Session, s: InterviewSession, out: dict, dry_run: bool) -> None:
    """After the retention period the WORDS go too, not only the sound: what the candidate said (and the quotes taken from it) is replaced. The levels, the decision and who
    made it stay, so the audit trail does. Idempotent: a transcript already cleared is not counted again."""
    cleared = 0
    st = s.state or {}
    for t in st.get("turns", []):
        for a in t.get("answers", []):
            if a.get("text") != GONE:
                cleared += 1
                if not dry_run:
                    a["text"] = GONE
        sc = t.get("score") or {}
        if sc.get("quote") and not dry_run:
            sc["quote"] = ""
    if cleared and not dry_run:
        from sqlalchemy.orm.attributes import flag_modified

        s.state = st
        flag_modified(s, "state")
        db.add(DecisionLog(actor="system", action="interview transcript deleted", subject=f"interview:{s.id}", reason=f"older than the retention period of {get_settings().retention_days} days",
                           evidence={"answers_cleared": cleared, "candidate_id": s.candidate_id}))
        for h in db.scalars(select(HumanInterview).where(HumanInterview.candidate_id == s.candidate_id)):
            h.lines, h.events = None, None
    out["transcripts_cleared"] = out.get("transcripts_cleared", 0) + cleared


def _purge_cv_files(db: Session, now: datetime, days: int, out: dict, dry_run: bool) -> None:
    """CV files (and the text read from them) older than the retention period are deleted. Only files inside the platform's storage folder are touched."""
    from pathlib import Path

    storage = get_settings().storage_dir.resolve()
    out.setdefault("cv_files_deleted", 0)
    for c in db.scalars(select(Candidate)):
        applied = _aware(c.applied_at)
        if not c.cv_path or applied is None or now - applied <= timedelta(days=days):
            continue
        p = Path(c.cv_path)
        p = p if p.is_absolute() else Path.cwd() / p
        try:
            p.resolve().relative_to(storage)
        except ValueError:
            continue
        out["cv_files_deleted"] += 1
        if dry_run:
            continue
        p.unlink(missing_ok=True)
        c.cv_path = ""
        db.query(CvText).filter(CvText.candidate_id == c.id).delete()
        db.add(DecisionLog(actor="system", action="CV deleted after retention period", subject=f"candidate:{c.id}", reason=f"older than {days} days"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    init_db()
    with SessionLocal() as db:
        r = purge(db, dry_run=args.dry_run)
    print(("Would delete" if args.dry_run else "Deleted") + f" {r['files_deleted']} audio file(s) from {len(r['interviews'])} interview(s), clear {r['transcripts_cleared']} transcript answer(s) and delete "
          f"{r['cv_files_deleted']} CV file(s) older than {get_settings().retention_days} days.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
