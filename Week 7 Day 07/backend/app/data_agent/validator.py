"""Ticket ENG-701: check every query before it runs.

The model writes SQL; nothing it writes runs until check_query() says so. The checks read the query's structure
(sqlglot parses it, as DuckDB SQL), never its text, so a comment, a capital letter or a second statement hidden
after a semicolon cannot get past them.
"""

import sqlglot
from sqlglot import exp

from app.data_agent.models import Check


def _kind(stmt: exp.Expression) -> str:
    """What kind of statement this is, in capitals, for the refusal: DROP, DELETE, COPY, ATTACH…"""
    if isinstance(stmt, exp.Command):
        return str(stmt.this).split()[0].upper()
    return type(stmt).__name__.upper()


def _function_name(node: exp.Expression) -> str:
    if isinstance(node, exp.Anonymous):
        return str(node.this).lower()
    return node.sql_name().lower()


def check_query(sql: str, approved: list[str], max_rows: int = 1000, blocked_functions: list[str] = ()) -> Check:
    """Decide whether one query may run, and return it ready to run.

    Refuse (ok=False, sql="") with every reason that applies, in this order and word for word:
      1. It does not parse as DuckDB SQL:           "Not valid SQL: <the parser's first line>"
         (stop here)
      2. More than one statement:                    "One query at a time: found 2 statements"
         (stop here)
      3. It is not a query (SELECT, WITH … SELECT, UNION…):
                                                     "Only SELECT queries can run: found DROP"   (use _kind())
         (stop here)
      4. For each table it reads, in the order they appear, once each:
         - a table function, such as read_csv(…):    "Reads files or settings: read_csv is not allowed"
         - a table with no schema that is not a CTE:  "Name the schema: write caseflow.cases, not cases"
                                                      when an approved table has that name, else "Not an approved table: <name>"
         - a schema.table not in `approved`:          "Not an approved table: hr.analyst_pay"
      5. Any function in `blocked_functions`, anywhere in the query, once each:
                                                     "Reads files or settings: getenv is not allowed"

    Allow (ok=True) and return the query as DuckDB SQL (pretty-printed, comments removed) with a limit on the outermost query:
      - no LIMIT:            add LIMIT max_rows, note "Added LIMIT 1000"
      - LIMIT above max_rows: lower it, note "Lowered LIMIT 50000 to 1000"
      - LIMIT at or below:   leave it, no note
    """
    try:
        stmts = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None and not isinstance(s, exp.Semicolon)]
    except sqlglot.errors.SqlglotError as e:
        first = str(e).strip().splitlines()[0] if str(e).strip() else "could not parse"
        return Check(ok=False, reasons=[f"Not valid SQL: {first}"])
    if not stmts:
        return Check(ok=False, reasons=["Not valid SQL: empty query"])
    if len(stmts) > 1:
        return Check(ok=False, reasons=[f"One query at a time: found {len(stmts)} statements"])
    stmt = stmts[0]
    if not isinstance(stmt, exp.Query):
        return Check(ok=False, reasons=[f"Only SELECT queries can run: found {_kind(stmt)}"])

    reasons: list[str] = []

    def add(r: str) -> None:
        if r not in reasons:
            reasons.append(r)

    ctes = {c.alias_or_name.lower() for c in stmt.find_all(exp.CTE)}
    approved_l = {a.lower() for a in approved}
    for t in stmt.find_all(exp.Table, bfs=False):
        if not isinstance(t.this, exp.Identifier):  # read_csv(...), duckdb_settings(): a function used as a table
            add(f"Reads files or settings: {_function_name(t.this)} is not allowed")
            continue
        schema, name = (t.db or ""), t.name
        if not schema:
            if name.lower() in ctes:
                continue
            match = [a for a in approved if a.lower().endswith("." + name.lower())]
            add(f"Name the schema: write {match[0]}, not {name}" if match else f"Not an approved table: {name}")
        elif f"{schema}.{name}".lower() not in approved_l:
            add(f"Not an approved table: {schema}.{name}")

    blocked = {b.lower() for b in blocked_functions}
    for f in stmt.find_all(exp.Func, bfs=False):
        if _function_name(f) in blocked:
            add(f"Reads files or settings: {_function_name(f)} is not allowed")
    if reasons:
        return Check(ok=False, reasons=reasons)

    notes: list[str] = []
    limit = stmt.args.get("limit")
    lit = limit.expression if limit is not None else None
    if limit is None:
        stmt = stmt.limit(max_rows)
        notes.append(f"Added LIMIT {max_rows}")
    elif isinstance(lit, exp.Literal) and not lit.is_string and int(float(lit.this)) > max_rows:
        notes.append(f"Lowered LIMIT {lit.this} to {max_rows}")
        stmt = stmt.limit(max_rows)
    return Check(ok=True, notes=notes, sql=stmt.sql(dialect="duckdb", pretty=True, comments=False))
