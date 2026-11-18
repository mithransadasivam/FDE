"""Day 7 smoke tests: they pass before and after the tickets. Run: python -m pytest -q tests/test_data_smoke.py"""

import json

import duckdb
import pytest
from fastapi.testclient import TestClient

from app.config import QUESTIONS_FILE_7, REPO
from app.data_agent import access, agent, semantic, warehouse
from app.data_agent.evaluate import same_result
from app.main import app

client = TestClient(app)


def test_the_warehouse_holds_18_months_of_caseflow():
    t = {x["table"]: x["rows"] for x in warehouse.tables()}
    assert len(t) == 9 and t["caseflow.cases"] == 23564 and t["caseflow.documents"] == 65117
    assert warehouse.run("SELECT COUNT(*) FROM caseflow.documents WHERE reviewed_at IS NOT NULL")["rows"] == [[60957]]


def test_the_connection_cannot_change_data_read_files_or_change_settings():
    con = warehouse.connect()
    for sql in ["DROP TABLE caseflow.cases", "SELECT * FROM read_csv('/etc/passwd')", "SET enable_external_access = true"]:
        with pytest.raises(duckdb.Error):
            con.execute(sql)
    con.close()


def test_the_cost_check_stops_a_cross_join():
    with pytest.raises(warehouse.QueryRefused, match="4.2 billion"):
        warehouse.run("SELECT COUNT(*) FROM caseflow.documents a, caseflow.documents b")


def test_the_time_limit_stops_a_slow_query():
    with pytest.raises(warehouse.QueryFailed, match="time limit"):
        warehouse.run("SELECT SUM(i) FROM range(20000000000) t(i)", timeout_s=0.3, max_scanned=10**13)


def test_semantic_layer_v1_describes_the_tables_and_has_no_terms():
    v1 = semantic.load("caseflow_v1")
    assert v1["terms"] == {} and len(v1["tables"]) == 7 and v1["as_of"] == "2026-10-30"
    text = semantic.render(v1)
    assert "### caseflow.cases" in text and "working_days_open" in text and "The bank's terms" not in text


def test_three_people_three_scopes():
    assert access.teams_for(access.user("tom.reyes")) == ["N1"]
    assert access.teams_for(access.user("grace.mensah")) == ["N1", "N2"]
    assert access.teams_for(access.user("helen.achebe")) is None
    assert access.masked_for(access.user("helen.achebe")) == ["caseflow.customers.customer_name"]


def test_the_question_sets_have_the_banks_answers():
    qs = json.loads(QUESTIONS_FILE_7.read_text())["questions"]
    assert len(qs) == 30 and all(q["expected"]["rows"] for q in qs)
    assert next(q for q in qs if q["id"] == "Q10")["expected"]["rows"] == [[4160]]
    hw = json.loads((REPO / "data" / "Day07_HW_Slide03_questions.json").read_text())["questions"]
    assert len(hw) == 20


def test_answers_are_compared_by_value_not_by_column_name():
    assert same_result([[7.0]], [[7]])
    assert same_result([["North 1", 8.0]], [[8.0, "north 1", 123]])
    assert not same_result([[4160]], [[1943]])
    assert not same_result([["a"], ["b"]], [["a"]])


def test_the_scripted_model_replies_for_the_terms_the_layer_defines():
    assert agent.scripted_task("Q07", semantic.load("caseflow_v1")) == "data_agent/Q07"
    assert agent.scripted_task("Q07", {"terms": {"turnaround": {}}, "examples": []}) == "data_agent/Q07+turnaround"
    assert agent.scripted_task("Q22", semantic.load("caseflow_v1"), repair=True) == "data_agent/Q22.repair"


def test_status_lists_the_people_layers_and_tickets():
    s = client.get("/api/data/status").json()
    assert [u["id"] for u in s["users"]] == ["tom.reyes", "grace.mensah", "helen.achebe"]
    assert "caseflow_v1" in s["layers"] and set(s["not_built"]) == {"validator", "row_security"}
