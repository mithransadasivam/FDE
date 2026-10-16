"""The vendor master, the watch list and the bank accounts (SQLite).

Private columns (policy §10.1): bank_accounts.account_number and bank_accounts.sort_code. They are refused by
the database layer itself: every read connection installs a SQLite authorizer that denies reading them, so even a
hand-written `SELECT *` or `SELECT account_number ...` fails. Matching a bank account is done on a salted hash
(bank_accounts.account_hash), which is not private.
"""
import csv
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from vendor_desk import config

PRIVATE_COLUMNS = {("bank_accounts", "account_number"), ("bank_accounts", "sort_code")}
_SALT = "marlowe-finch-demo-salt"

SCHEMA = """
CREATE TABLE vendors (
    vendor_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    registered_country TEXT NOT NULL,
    tax_id TEXT NOT NULL,
    payment_terms_days INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT,
    source_case TEXT
);
CREATE TABLE bank_accounts (
    vendor_id TEXT NOT NULL REFERENCES vendors(vendor_id),
    bank_name TEXT,
    bank_country TEXT NOT NULL,
    account_number TEXT NOT NULL,   -- PRIVATE
    sort_code TEXT,                 -- PRIVATE
    account_hash TEXT NOT NULL      -- salted hash, safe to compare
);
CREATE TABLE watchlist (
    entry_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    reason TEXT,
    listed_on TEXT
);
CREATE TABLE vendor_creations (
    case_id TEXT PRIMARY KEY,       -- the idempotency key: one vendor per case
    vendor_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    approvers TEXT NOT NULL
);
"""


def account_hash(account_number: str) -> str:
    return hashlib.sha256((_SALT + account_number.strip()).encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_database(db_path: Path | str | None = None, seed_dir: Path | str | None = None) -> dict:
    """Build the database from scratch from the seed files and return the row counts. Safe to run again."""
    db_path = Path(db_path or config.db_path())
    seed_dir = Path(seed_dir or config.SEED_DIR)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    with closing(sqlite3.connect(db_path)) as con:
        con.executescript(SCHEMA)
        with open(seed_dir / "vendors.csv", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                con.execute(
                    "INSERT INTO vendors(vendor_id,name,registered_country,tax_id,payment_terms_days,status,created_at)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (r["vendor_id"], r["name"], r["registered_country"], r["tax_id"], int(r["payment_terms_days"]),
                     r["status"], "2024-01-01T00:00:00+00:00"),
                )
                con.execute(
                    "INSERT INTO bank_accounts VALUES (?,?,?,?,?,?)",
                    (r["vendor_id"], r["bank_name"], r["bank_country"], r["account_number"], r["sort_code"],
                     account_hash(r["account_number"])),
                )
        with open(seed_dir / "watchlist.csv", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                con.execute("INSERT INTO watchlist VALUES (?,?,?,?)",
                            (r["entry_id"], r["name"], r["reason"], r["listed_on"]))
        con.commit()
        return counts(con)


def counts(con: sqlite3.Connection) -> dict:
    return {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("vendors", "bank_accounts", "watchlist", "vendor_creations")}


def _authorizer(action, arg1, arg2, dbname, source):
    """Deny the private columns and everything that is not a plain read."""
    if action == sqlite3.SQLITE_READ:
        if (arg1, arg2) in PRIVATE_COLUMNS:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE):
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def connect_readonly(db_path: Path | str | None = None) -> sqlite3.Connection:
    """A read-only connection that cannot read the private columns (database-layer enforcement)."""
    path = Path(db_path or config.db_path())
    if not path.exists():
        raise FileNotFoundError(f"The vendor database {path.name} does not exist. Run: python -m scripts.build_db")
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.set_authorizer(_authorizer)
    return con


def connect_write(db_path: Path | str | None = None) -> sqlite3.Connection:
    con = sqlite3.connect(Path(db_path or config.db_path()))
    con.row_factory = sqlite3.Row
    return con


def run_select(sql: str, db_path=None, max_rows: int = 50) -> dict:
    """Run one SELECT for a model or a person. Anything else, or any private column, is refused with a readable
    message. Returns {"columns": [...], "rows": [...], "truncated": bool}."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped.lower().startswith(("select", "with")) or ";" in stripped:
        raise QueryRefused("Only a single SELECT query is allowed.")
    with closing(connect_readonly(db_path)) as con:
        try:
            cur = con.execute(stripped)
            fetched = cur.fetchmany(max_rows + 1)
        except sqlite3.DatabaseError as err:
            msg = str(err)
            if "not authorized" in msg or "prohibited" in msg:
                raise QueryRefused(
                    "Refused: that query reads a private column (bank account number or sort code). "
                    "Policy §10.1 says these are never available. Ask for the bank country instead."
                ) from err
            raise QueryRefused(f"The query could not run: {msg}") from err
        cols = [d[0] for d in cur.description or []]
        return {"columns": cols, "rows": [list(r) for r in fetched[:max_rows]], "truncated": len(fetched) > max_rows}


class QueryRefused(Exception):
    """A query that the database layer or the query checker will not run."""


def create_vendor_record(case_id: str, name: str, registered_country: str, tax_id: str, payment_terms_days: int,
                         bank_name: str, bank_country: str, account_number: str, sort_code: str,
                         approvers: list[str], db_path=None) -> dict:
    """The one write. Idempotent: calling it again for the same case id returns the same vendor and writes nothing."""
    with closing(connect_write(db_path)) as con:
        con.execute("BEGIN IMMEDIATE")
        existing = con.execute("SELECT vendor_id FROM vendor_creations WHERE case_id = ?", (case_id,)).fetchone()
        if existing:
            con.rollback()
            return {"vendor_id": existing["vendor_id"], "created": False, "case_id": case_id}
        last = con.execute("SELECT MAX(CAST(SUBSTR(vendor_id, 5) AS INTEGER)) FROM vendors").fetchone()[0] or 1000
        vendor_id = f"VEN-{last + 1}"
        now = _now()
        con.execute("INSERT INTO vendors VALUES (?,?,?,?,?,?,?,?)",
                    (vendor_id, name, registered_country, tax_id, payment_terms_days, "active", now, case_id))
        con.execute("INSERT INTO bank_accounts VALUES (?,?,?,?,?,?)",
                    (vendor_id, bank_name, bank_country, account_number, sort_code, account_hash(account_number)))
        con.execute("INSERT INTO vendor_creations VALUES (?,?,?,?)",
                    (case_id, vendor_id, now, json.dumps(approvers)))
        con.commit()
        return {"vendor_id": vendor_id, "created": True, "case_id": case_id}
