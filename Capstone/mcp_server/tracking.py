"""The fictional tracking system: a SQLite database of requisitions, candidates, stages and interviews.

Rule 9 (least privilege): private columns (name, contact details, address, date of birth, salary expectation) are refused by the
DATABASE, not just left out of a description. Every connection is opened read-only and with a SQLite authorizer that denies
any read of a private column; the tools also check column names against a whitelist before building SQL, and bind every value
as a parameter, so a SQL-injection string cannot reach a private column either.
"""
import sqlite3
from pathlib import Path

PRIVATE_COLUMNS = {"name", "email", "phone", "address", "date_of_birth", "salary_expectation"}
PUBLIC_COLUMNS = ["id", "requisition_id", "stage", "current_title", "years_experience", "skills", "certifications", "education", "cv_format"]


class AccessRefused(Exception):
    """A tool asked for something private. The message is safe to show."""


def _authorizer(action, arg1, arg2, db_name, source):
    if action == sqlite3.SQLITE_READ and arg2 in PRIVATE_COLUMNS and arg1 == "candidates":
        return sqlite3.SQLITE_DENY  # the database refuses, whatever the SQL says
    if action in (sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE, sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_CREATE_TABLE,
                  sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_PRAGMA):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def connect(path: str | Path) -> sqlite3.Connection:
    """A read-only connection with the private-column authorizer."""
    uri = f"file:{Path(path).resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.set_authorizer(_authorizer)
    return conn


def _run(path, sql: str, params: tuple = ()) -> list[dict]:
    conn = connect(path)
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    except sqlite3.DatabaseError as e:
        if "prohibited" in str(e) or "not authorized" in str(e):
            raise AccessRefused("That information is private and the tracking system refuses to return it.") from e
        raise
    finally:
        conn.close()


def check_columns(columns: list[str] | None) -> list[str]:
    cols = columns or ["id", "stage", "current_title", "years_experience", "skills"]
    bad = [c for c in cols if c not in PUBLIC_COLUMNS]
    if bad:
        if any(c in PRIVATE_COLUMNS for c in bad):
            raise AccessRefused(f"Private column(s) refused: {', '.join(b for b in bad if b in PRIVATE_COLUMNS)}")
        raise AccessRefused(f"Unknown column(s): {', '.join(bad)}")
    return cols


def list_requisitions(path) -> list[dict]:
    return _run(path, "SELECT r.id, r.title, r.status, (SELECT COUNT(*) FROM candidates c WHERE c.requisition_id = r.id) AS candidates FROM requisitions r ORDER BY r.id")


def get_candidate(path, candidate_id: int, columns: list[str] | None = None) -> dict | None:
    cols = check_columns(columns)
    rows = _run(path, f"SELECT {', '.join(cols)} FROM candidates WHERE id = ?", (candidate_id,))
    return rows[0] if rows else None


def search_candidates(path, skill: str | None = None, stage: str | None = None, min_years: float | None = None,
                      requisition_id: int | None = None, limit: int = 20) -> list[dict]:
    where, params = [], []
    if skill:
        where.append("LOWER(skills) LIKE ?")
        params.append(f"%{skill.lower()}%")  # bound as a parameter: it is never part of the SQL text
    if stage:
        where.append("stage = ?")
        params.append(stage)
    if min_years is not None:
        where.append("years_experience >= ?")
        params.append(min_years)
    if requisition_id is not None:
        where.append("requisition_id = ?")
        params.append(requisition_id)
    sql = "SELECT id, requisition_id, stage, current_title, years_experience, skills FROM candidates"
    if where:
        sql += " WHERE " + " AND ".join(where)
    return _run(path, sql + " ORDER BY id LIMIT ?", (*params, max(1, min(limit, 100))))


def interviews_for(path, candidate_id: int) -> list[dict]:
    return _run(path, "SELECT id, candidate_id, kind, status, score FROM interviews WHERE candidate_id = ? ORDER BY id", (candidate_id,))


# ---- building the database from the platform's own data (the tracking system is fed by the platform) -------------------------------
SCHEMA = """
CREATE TABLE requisitions (id INTEGER PRIMARY KEY, title TEXT, status TEXT);
CREATE TABLE candidates (id INTEGER PRIMARY KEY, requisition_id INTEGER, stage TEXT, current_title TEXT, years_experience REAL,
    skills TEXT, certifications TEXT, education TEXT, cv_format TEXT,
    name TEXT, email TEXT, phone TEXT, address TEXT, date_of_birth TEXT, salary_expectation INTEGER);
CREATE TABLE stages (candidate_id INTEGER, stage TEXT, at TEXT, actor TEXT);
CREATE TABLE interviews (id INTEGER PRIMARY KEY, candidate_id INTEGER, kind TEXT, status TEXT, score REAL);
"""


def export_from_app(db, path: str | Path) -> Path:
    """Writes the tracking-system database from the platform's data. Private columns are filled in (the database refuses to
    return them to the tools). Salary expectations are made up: every candidate in this project is fictional."""
    from app.models import Candidate, DecisionLog, Requisition
    from app.models_ext import InterviewSession
    from sqlalchemy import select

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.unlink(missing_ok=True)
    conn = sqlite3.connect(p)
    conn.executescript(SCHEMA)
    for r in db.scalars(select(Requisition)):
        conn.execute("INSERT INTO requisitions VALUES (?,?,?)", (r.id, r.title, r.status))
    val = lambda prof, k: ((prof or {}).get(k) or {}).get("value")  # noqa: E731
    for c in db.scalars(select(Candidate)):
        pr = c.profile or {}
        conn.execute("INSERT INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            c.id, c.requisition_id, c.stage, val(pr, "current_title"), val(pr, "years_experience"), "; ".join(val(pr, "skills") or []),
            "; ".join(val(pr, "certifications") or []), val(pr, "education"), c.cv_format, val(pr, "name"), val(pr, "email"), val(pr, "phone"),
            val(pr, "address"), val(pr, "date_of_birth"), 28000 + (c.id * 1731) % 30000))
        for log in db.scalars(select(DecisionLog).where(DecisionLog.subject == f"candidate:{c.id}", DecisionLog.action.like("move %"))):
            conn.execute("INSERT INTO stages VALUES (?,?,?,?)", (c.id, log.action.split("-> ")[-1], str(log.at), log.actor))
    for s in db.scalars(select(InterviewSession)):
        conn.execute("INSERT INTO interviews (candidate_id, kind, status, score) VALUES (?,?,?,?)",
                     (s.candidate_id, "ai_first_round", s.status, (s.scorecard or {}).get("total")))
    conn.commit()
    conn.close()
    return p
