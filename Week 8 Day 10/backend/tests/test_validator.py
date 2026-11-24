"""Ticket ENG-701: check every query before it runs. Run: python -m pytest -q tests/test_validator.py"""

import pytest
from fastapi.testclient import TestClient

from app.data_agent.validator import check_query
from app.main import app

APPROVED = ["caseflow.cases", "caseflow.documents", "caseflow.customers", "caseflow.analysts"]
BLOCKED = ["read_csv", "getenv", "glob"]


def check(sql, max_rows=1000):
    return check_query(sql, APPROVED, max_rows, BLOCKED)


def test_a_select_passes_with_a_limit_added():
    c = check("select status, count(*) from caseflow.cases group by status")
    assert c.ok and c.reasons == [] and c.notes == ["Added LIMIT 1000"]
    assert c.sql.startswith("SELECT") and c.sql.rstrip().endswith("LIMIT 1000")


def test_a_limit_above_the_maximum_is_lowered_and_a_small_one_kept():
    c = check("SELECT * FROM caseflow.cases LIMIT 50000")
    assert c.ok and c.notes == ["Lowered LIMIT 50000 to 1000"] and "LIMIT 1000" in c.sql and "50000" not in c.sql
    c = check("SELECT * FROM caseflow.cases LIMIT 10")
    assert c.ok and c.notes == [] and "LIMIT 10" in c.sql


@pytest.mark.parametrize("sql,kind", [
    ("DROP TABLE caseflow.cases", "DROP"), ("DELETE FROM caseflow.documents", "DELETE"),
    ("UPDATE caseflow.cases SET status = 'approved'", "UPDATE"), ("INSERT INTO caseflow.cases VALUES (1)", "INSERT"),
    ("CREATE TABLE caseflow.x AS SELECT 1", "CREATE"), ("COPY (SELECT * FROM caseflow.customers) TO 'x.csv'", "COPY"),
    ("ATTACH 'other.duckdb' AS other", "ATTACH"), ("PRAGMA version", "PRAGMA"),
])
def test_anything_but_a_query_is_refused(sql, kind):
    c = check(sql)
    assert not c.ok and c.reasons == [f"Only SELECT queries can run: found {kind}"] and c.sql == ""


def test_a_second_statement_is_refused_even_after_a_comment():
    assert check("SELECT 1; DROP TABLE caseflow.cases").reasons == ["One query at a time: found 2 statements"]
    assert check("SELECT COUNT(*) FROM caseflow.cases; -- harmless\nDELETE FROM caseflow.cases").reasons == ["One query at a time: found 2 statements"]
    assert check("SELECT COUNT(*) FROM caseflow.cases -- ; DROP TABLE caseflow.cases").ok


def test_tables_that_are_not_approved_are_refused_wherever_they_are():
    assert check("SELECT * FROM hr.analyst_pay").reasons == ["Not an approved table: hr.analyst_pay"]
    assert check("WITH p AS (SELECT * FROM hr.analyst_pay) SELECT * FROM p").reasons == ["Not an approved table: hr.analyst_pay"]
    assert check("SELECT * FROM caseflow.cases WHERE case_id IN (SELECT case_id FROM staging.caseflow_raw)").reasons == \
        ["Not an approved table: staging.caseflow_raw"]
    assert check("SELECT * FROM information_schema.tables").reasons == ["Not an approved table: information_schema.tables"]


def test_cte_names_are_allowed_and_a_missing_schema_is_explained():
    assert check("WITH c AS (SELECT * FROM caseflow.cases) SELECT COUNT(*) FROM c").ok
    assert check("SELECT COUNT(*) FROM cases").reasons == ["Name the schema: write caseflow.cases, not cases"]
    assert check("SELECT * FROM '/etc/passwd'").reasons == ["Not an approved table: /etc/passwd"]


def test_functions_that_read_files_or_settings_are_refused():
    assert check("SELECT * FROM read_csv('/etc/passwd')").reasons == ["Reads files or settings: read_csv is not allowed"]
    assert check("SELECT * FROM duckdb_settings()").reasons == ["Reads files or settings: duckdb_settings is not allowed"]
    assert check("SELECT COUNT(*) FROM caseflow.cases WHERE getenv('HOME') IS NOT NULL").reasons == \
        ["Reads files or settings: getenv is not allowed"]


def test_every_reason_is_given_once_in_order():
    c = check("SELECT * FROM hr.analyst_pay a JOIN read_csv('x.csv') r ON TRUE JOIN hr.analyst_pay b ON TRUE WHERE getenv('X') = '1'")
    assert c.reasons == ["Not an approved table: hr.analyst_pay", "Reads files or settings: read_csv is not allowed",
                         "Reads files or settings: getenv is not allowed"]


def test_sql_that_does_not_parse_is_refused():
    c = check("SELECT FROM WHERE (")
    assert not c.ok and c.reasons[0].startswith("Not valid SQL")


def test_a_union_gets_one_limit():
    c = check("SELECT team_id FROM caseflow.cases UNION SELECT team_id FROM caseflow.analysts")
    assert c.ok and c.sql.count("LIMIT") == 1


def test_the_safety_tab_refuses_15_and_allows_3():
    s = TestClient(app).get("/api/data/probes").json()
    assert s["not_built"] == "" and s["summary"]["passed"] == 18 and s["summary"]["by_cost_check"] == 1
