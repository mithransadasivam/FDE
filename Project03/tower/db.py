"""SQLite layer: builds data/tower.db from the starter CSV files and holds runtime tables.

personal_mobile is stored in `oncall_private`, a table no tool, index or prompt is given (policy 7.3).
Everything else about an engineer lives in `oncall`.
"""
from __future__ import annotations

import csv
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .settings import ROOT

SCHEMA = """
CREATE TABLE services(service_id TEXT PRIMARY KEY, name TEXT, tier INTEGER, owner_team TEXT, depends_on TEXT, runbooks TEXT);
CREATE TABLE oncall(team TEXT PRIMARY KEY, engineer TEXT, work_email TEXT);
CREATE TABLE oncall_private(team TEXT PRIMARY KEY, personal_mobile TEXT);
CREATE TABLE alerts(alert_id TEXT PRIMARY KEY, time TEXT, source TEXT, service TEXT, "check" TEXT, severity TEXT, status TEXT, message TEXT);
CREATE TABLE past_incidents(incident_id TEXT PRIMARY KEY, opened TEXT, service TEXT, symptom TEXT, severity TEXT,
    root_cause_service TEXT, fixed_by TEXT, minutes_to_resolve INTEGER, notes TEXT);
CREATE TABLE incidents(incident_id TEXT PRIMARY KEY, opened TEXT, severity TEXT, status TEXT, root_cause TEXT,
    data TEXT NOT NULL, updated TEXT);
CREATE TABLE action_requests(request_id TEXT PRIMARY KEY, incident_id TEXT, runbook_id TEXT, step_no INTEGER, action TEXT,
    target_service TEXT, reason TEXT, status TEXT, required TEXT, created TEXT, executed TEXT);
CREATE TABLE approvals(id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT, approver TEXT, decision TEXT, reason TEXT, ts TEXT,
    UNIQUE(request_id, approver));
CREATE TABLE audit(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor TEXT, event TEXT, detail TEXT);
CREATE TABLE replay(alert_id TEXT PRIMARY KEY, seq INTEGER);
"""

# tables the model and its tools can never be given
PRIVATE_TABLES = {"oncall_private"}


def _rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _deny_private(action, arg1, arg2, dbname, source):
    """SQLite authorizer: reading any column of a private table is refused at the database layer, whatever the SQL says."""
    if action == sqlite3.SQLITE_READ and arg1 in PRIVATE_TABLES:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def connect(db_path: Path, restricted: bool = False) -> sqlite3.Connection:
    """restricted=True is what the application and every tool get: oncall_private cannot be read through it."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path, timeout=15, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=10000")
    if restricted:
        con.set_authorizer(_deny_private)
    return con


def load_private_for_redaction(db_path: Path) -> list[str]:
    """The ONE place personal_mobile is read: so the redactor can recognise and hide those exact values. Never shown or sent."""
    con = connect(db_path)
    try:
        return [r[0] for r in con.execute("SELECT personal_mobile FROM oncall_private")]
    finally:
        con.close()


@contextmanager
def tx(con: sqlite3.Connection):
    """One write transaction that takes the lock first, so two approvals cannot interleave."""
    con.execute("BEGIN IMMEDIATE")
    try:
        yield con
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise


def build(db_path: Path, data_dir: Path | None = None) -> dict[str, int]:
    """Drop and rebuild the database from the CSV files. Safe to run again any time."""
    data_dir = Path(data_dir or ROOT / "data")
    db_path = Path(db_path)
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink()
    con = connect(db_path)
    con.executescript(SCHEMA)
    for r in _rows(data_dir / "services.csv"):
        con.execute("INSERT INTO services VALUES(?,?,?,?,?,?)",
                    (r["service_id"], r["name"], int(r["tier"]), r["owner_team"], r["depends_on"], r["runbooks"]))
    for r in _rows(data_dir / "oncall.csv"):
        con.execute("INSERT INTO oncall VALUES(?,?,?)", (r["team"], r["engineer"], r["work_email"]))
        con.execute("INSERT INTO oncall_private VALUES(?,?)", (r["team"], r["personal_mobile"]))
    for r in _rows(data_dir / "alerts.csv"):
        con.execute("INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?)",
                    (r["alert_id"], r["time"], r["source"], r["service"], r["check"], r["severity"], r["status"], r["message"]))
    for r in _rows(data_dir / "incidents_history.csv"):
        con.execute("INSERT INTO past_incidents VALUES(?,?,?,?,?,?,?,?,?)",
                    (r["incident_id"], r["opened"], r["service"], r["symptom"], r["severity"], r["root_cause_service"],
                     r["fixed_by"], int(r["minutes_to_resolve"]), r["notes"]))
    con.commit()
    counts = counts_of(con)
    con.close()
    return counts


def counts_of(con: sqlite3.Connection) -> dict[str, int]:
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("services", "oncall", "alerts", "past_incidents")}


def ensure(db_path: Path) -> None:
    """Build the database if it is missing (first start in a fresh container)."""
    if not Path(db_path).exists():
        build(db_path)
