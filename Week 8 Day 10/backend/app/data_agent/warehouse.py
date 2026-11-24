"""The client's warehouse, on your laptop: DuckDB built from the bank's CaseFlow extract (done, not a ticket).

    data/Day07_Slide10_warehouse/<schema>.<table>.parquet   the extract, as the bank's MI team sent it
    engagement/data_agent/warehouse.duckdb                  the warehouse, built from it once

The data agent only ever opens the warehouse read-only, with file access switched off, and every query also passes a
cost check and a time limit. These are the layers under the validator (ENG-701) and row security (ENG-702): if one
of those has a bug, a DROP or a read_csv('/etc/passwd') still cannot work.

In production the same code points at the bank's warehouse (Snowflake or Databricks) with a read-only service role.
"""

import json
import math
import threading
import time
from pathlib import Path

import duckdb

from app import store
from app.config import WAREHOUSE_FILES_7

MAX_ROWS_SCANNED = 10_000_000   # the cost check: refuse a query the planner expects to touch more rows than this
TIMEOUT_S = 5                   # stop any query that runs longer than this
_lock = threading.RLock()
_db: duckdb.DuckDBPyConnection | None = None  # one read-only database per process; each query gets its own cursor


class QueryRefused(RuntimeError):
    """The cost check refused the query before it ran."""


class QueryFailed(RuntimeError):
    """The warehouse could not run the query: a bad column, a bad function, or the time limit."""


def db_path() -> Path:
    return store.path("data_agent/warehouse.duckdb")


def build(force: bool = False) -> Path:
    """Build engagement/data_agent/warehouse.duckdb from the parquet files (about a second), once."""
    p = db_path()
    with _lock:
        if p.exists() and not force:
            return p
        tmp = p.with_suffix(".building")
        tmp.unlink(missing_ok=True)
        con = duckdb.connect(str(tmp))
        for f in sorted(WAREHOUSE_FILES_7.glob("*.parquet")):
            schema, table = f.stem.split(".")
            con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
            con.execute(f"CREATE TABLE {schema}.{table} AS SELECT * FROM read_parquet('{f.as_posix()}')")
        con.close()
        tmp.replace(p)
    return p


def connect() -> duckdb.DuckDBPyConnection:
    """A cursor on the read-only warehouse, which cannot read or write files, change settings or use more than 2 threads.
    The settings belong to the database, so they are made once, then locked."""
    global _db
    with _lock:
        if _db is None:
            db = duckdb.connect(str(build()), read_only=True)
            db.execute("SET threads = 2")
            db.execute("SET memory_limit = '1GB'")
            db.execute("SET enable_external_access = false")
            db.execute("SET lock_configuration = true")
            _db = db
        return _db.cursor()


def tables() -> list[dict]:
    """Every table in the warehouse, approved or not, with its row count and columns."""
    con = connect()
    rows = con.execute("SELECT table_schema, table_name FROM information_schema.tables ORDER BY 1, 2").fetchall()
    out = []
    for schema, name in rows:
        cols = con.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = ? AND table_name = ? "
                           "ORDER BY ordinal_position", [schema, name]).fetchall()
        n = con.execute(f"SELECT COUNT(*) FROM {schema}.{name}").fetchone()[0]
        out.append({"table": f"{schema}.{name}", "rows": n, "columns": [{"name": c, "type": t} for c, t in cols]})
    con.close()
    return out


def _estimate(node: dict) -> float:
    kids = [_estimate(c) for c in node.get("children", [])]
    own = node.get("extra_info", {}).get("Estimated Cardinality")
    if node.get("name") == "CROSS_PRODUCT":
        return math.prod(kids) if kids else 0
    here = float(own) if own not in (None, "", "0") else 0
    return max([here, *kids]) if kids else here


def estimate_rows(con, sql: str) -> int:
    """The most rows any step of the planner's plan expects (a cross join multiplies its two sides)."""
    plan = json.loads(con.execute("EXPLAIN (FORMAT JSON) " + sql).fetchall()[0][1])
    return int(max(_estimate(n) for n in plan))


def _words(n: int) -> str:
    return f"{n / 1e9:.1f} billion" if n >= 1e9 else f"{n / 1e6:.1f} million" if n >= 1e6 else f"{n:,}"


def run(sql: str, timeout_s: float = TIMEOUT_S, max_scanned: int = MAX_ROWS_SCANNED) -> dict:
    """Run one checked query. Returns {"columns", "rows", "ms", "estimated_rows"}.
    Raises QueryRefused (cost check) or QueryFailed (any error, or the time limit)."""
    con = connect()
    try:
        try:
            est = estimate_rows(con, sql)
        except duckdb.Error as e:
            raise QueryFailed(_short(e)) from e
        if est > max_scanned:
            raise QueryRefused(f"Too costly: the plan touches about {_words(est)} rows, and the limit is {_words(max_scanned)}")
        timer = threading.Timer(timeout_s, con.interrupt)
        started = time.perf_counter()
        timer.start()
        try:
            cur = con.execute(sql)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
        except duckdb.InterruptException as e:
            raise QueryFailed(f"Stopped after {timeout_s:g} seconds: the time limit") from e
        except duckdb.Error as e:
            raise QueryFailed(_short(e)) from e
        finally:
            timer.cancel()
        return {"columns": cols, "rows": [[_plain(v) for v in r] for r in rows], "ms": round((time.perf_counter() - started) * 1000),
                "estimated_rows": est}
    finally:
        con.close()


def _short(e: Exception) -> str:
    return str(e).strip().split("\n")[0][:300]


def _plain(v):
    """Values the screens and JSON files can hold."""
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return round(v, 4)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    try:
        return float(v)  # Decimal
    except (TypeError, ValueError):
        return str(v)
