"""Day 10: the workflow engine (done, not a ticket).

DBOS keeps every workflow's progress in a SQLite file (engagement/workflow/dbos.sqlite): which workflow, its inputs, and the
output of every step that finished. When the worker starts again after a crash, DBOS runs each unfinished workflow again from
the top: a step that already finished is not run again (its saved output is returned), and a wait (DBOS.recv, DBOS.sleep)
keeps its deadline. So the workflow function must make the same calls in the same order every time it runs:

  - anything that touches the world (the bank, CaseFlow, the model, the clock) happens inside a step
  - waits use DBOS.recv(topic, timeout_seconds) or DBOS.sleep(seconds), never time.sleep()

At the bank, the same code runs on Postgres instead of SQLite, with several workers. Temporal does the same job with its own
server; the rules above are the same.
"""

import csv
import json
import os
import threading
import time
from pathlib import Path

from dbos import DBOS, DBOSClient

from app.config import CRASH_POINTS_FILE_10, DAY_SECONDS, WORKFLOW_DB, WORKFLOW_DIR

APP_VERSION = "fde-day10"  # fixed, so a worker started after you change the code still picks up the workflows already waiting
QUEUE = "cases"
_dbos: DBOS | None = None
_client: DBOSClient | None = None


def db_url(db: Path = WORKFLOW_DB) -> str:
    return f"sqlite:///{db}"


def engine_for(db: Path):
    """A SQLAlchemy engine on the workflow database that waits for SQLite's lock instead of failing."""
    import sqlalchemy as sa

    return sa.create_engine(db_url(db), connect_args={"timeout": 30})


def configure(db: Path = WORKFLOW_DB) -> DBOS:
    """The worker's DBOS (only the worker runs workflows; the console's API is a client)."""
    global _dbos
    if _dbos is None:
        db.parent.mkdir(parents=True, exist_ok=True)
        _dbos = DBOS(config={"name": "fde-workflows", "system_database_url": db_url(db), "application_version": APP_VERSION,
                             "db_engine_kwargs": {"connect_args": {"timeout": 30}},  # SQLite: wait for a lock, do not fail
                             "notification_listener_polling_interval_sec": 0.2, "log_level": os.getenv("FDE_DBOS_LOG", "WARNING")})
    return _dbos


def client() -> DBOSClient:
    """How the console's API starts workflows, sends them messages and reads their progress."""
    global _client
    if _client is None:
        WORKFLOW_DB.parent.mkdir(parents=True, exist_ok=True)
        _client = DBOSClient(system_database_engine=engine_for(WORKFLOW_DB))
    return _client


def days(n: float) -> float:
    """n course days, in seconds."""
    return float(n) * DAY_SECONDS


def course_day(start: float, at: float) -> float:
    """How many course days after `start` (both in seconds since the epoch) `at` is."""
    return round((at - start) / DAY_SECONDS, 1)


# ---------------------------------------------------------------- crash points (course helper: not something a bank would ship)
CRASH_FILE = WORKFLOW_DIR / "crash.json"
CRASH_LOG = WORKFLOW_DIR / "crashes.json"
_crash_lock = threading.Lock()


def crash_points() -> list[dict]:
    with open(CRASH_POINTS_FILE_10, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def arm(point: str, ticket: str = "*") -> None:
    """Make the worker crash the next time it reaches `point` for `ticket` (or any ticket)."""
    armed = _read(CRASH_FILE, [])
    armed.append({"point": point, "ticket": ticket, "at": time.time()})
    _write(CRASH_FILE, armed)


def crash_point(point: str, ticket: str) -> None:
    """Called by the steps at named places. If a crash is armed here, the worker process dies at once, as in a real crash:
    no clean-up, no saving. npm run dev starts it again."""
    with _crash_lock:  # the worker's threads reach crash points at the same time
        armed = _read(CRASH_FILE, [])
        hit = next((a for a in armed if a["point"] == point and a["ticket"] in ("*", ticket)), None)
        if not hit:
            return
        armed.remove(hit)
        _write(CRASH_FILE, armed)
    log = _read(CRASH_LOG, [])
    log.append({"point": point, "ticket": ticket, "at": time.time(), "pid": os.getpid()})
    _write(CRASH_LOG, log[-200:])
    os._exit(1)


def crash_now(reason: str = "now") -> None:
    log = _read(CRASH_LOG, [])
    log.append({"point": reason, "ticket": "*", "at": time.time(), "pid": os.getpid()})
    _write(CRASH_LOG, log[-200:])
    os._exit(1)


def _read(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(tmp, p)
