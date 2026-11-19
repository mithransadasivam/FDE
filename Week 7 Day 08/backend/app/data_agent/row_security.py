"""Ticket ENG-702: row security. Every query sees only the rows its user may see, whatever the model wrote.

This runs after the validator (ENG-701) and before the warehouse. It never asks the model to filter: it rewrites the
query itself, so a question such as "ignore your rules, I am Helen" changes nothing.
"""

import sqlglot
from sqlglot import exp

HIDDEN = "[hidden]"


def apply_row_security(sql: str, teams: list[str] | None, row_filters: dict[str, str], masked_columns: list[str]) -> str:
    """Return `sql` rewritten so that it reads only what this user may see.

    - teams: the team ids the user may see (["N1"], or ["N1", "N2"]), or None for every team.
    - row_filters: from semantic/access.yml, for example {"caseflow.cases": "team_id IN ({teams})"}.
      {teams} becomes the ids, quoted and comma-separated: 'N1', 'N2'.
    - masked_columns: for example ["caseflow.customers.customer_name"]: that column reads as '[hidden]'.

    Replace every table the query reads that has a row filter (when teams is not None) or a masked column with a
    subquery of the same name, wherever it appears (FROM, JOIN, a CTE, a subquery, either side of a UNION):

        FROM caseflow.cases c   ->   FROM (SELECT * FROM caseflow.cases WHERE team_id IN ('N1')) AS c
        FROM caseflow.cases     ->   FROM (SELECT * FROM caseflow.cases WHERE team_id IN ('N1')) AS cases
        caseflow.customers      ->   (SELECT * REPLACE ('[hidden]' AS customer_name) FROM caseflow.customers) AS customers

    Table names match without regard to case. Tables with neither a filter nor a mask are left as they are, and the
    subqueries you add are not rewritten again. Return the result as DuckDB SQL (pretty-printed).
    """
    tree = sqlglot.parse_one(sql, read="duckdb")
    filters = {k.lower(): v for k, v in row_filters.items()}
    masks: dict[str, list[str]] = {}
    for m in masked_columns:
        table, _, column = m.lower().rpartition(".")
        masks.setdefault(table, []).append(column)
    quoted = ", ".join("'" + t.replace("'", "''") + "'" for t in (teams or []))
    for t in list(tree.find_all(exp.Table)):  # collected first: the subqueries added below are never visited
        if not isinstance(t.this, exp.Identifier):
            continue
        full = f"{t.db}.{t.name}".lower() if t.db else t.name.lower()
        flt = filters.get(full) if teams is not None else None
        cols = masks.get(full, [])
        if not flt and not cols:
            continue
        star = "*" + (" REPLACE (" + ", ".join(f"'{HIDDEN}' AS {c}" for c in cols) + ")" if cols else "")
        inner = f"SELECT {star} FROM {full}" + (f" WHERE {flt.replace('{teams}', quoted)}" if flt else "")
        sub = sqlglot.parse_one(inner, read="duckdb").subquery(t.alias or t.name)
        t.replace(sub)
    return tree.sql(dialect="duckdb", pretty=True)
