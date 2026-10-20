"""Activity 3: log_query() records every query the AI runs. Run: pytest tests/test_mcp_log.py"""

import json
from datetime import datetime

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from app.mcp_server import log_query, run_query
from tests.day13_helpers import read_log


def test_writes_one_json_line_and_creates_the_folder(tmp_path):
    log_file = tmp_path / "new_folder" / "q.jsonl"
    log_query("SELECT 1", 1, log_file=str(log_file))
    entry = json.loads(log_file.read_text(encoding="utf-8"))
    assert {k: entry[k] for k in ("sql", "rows", "error")} == {
        "sql": "SELECT 1",
        "rows": 1,
        "error": None,
    }
    assert datetime.fromisoformat(entry["time"]).tzinfo is not None


def test_appends_instead_of_overwriting(tmp_path):
    log_file = str(tmp_path / "q.jsonl")
    log_query("SELECT 1", 1, log_file=log_file)
    log_query("SELECT 2", 0, error="boom", log_file=log_file)
    with open(log_file, encoding="utf-8") as f:
        lines = f.read().splitlines()
    assert [json.loads(line)["sql"] for line in lines] == ["SELECT 1", "SELECT 2"]
    assert json.loads(lines[1])["error"] == "boom"


def test_never_prints(tmp_path, capsys):
    log_query("SELECT 1", 1, log_file=str(tmp_path / "q.jsonl"))
    assert capsys.readouterr().out == ""


def test_run_query_logs_each_successful_query_with_its_row_count(db):
    run_query("SELECT id FROM tickets WHERE severity = 'P1'", db)
    assert [(e["sql"], e["rows"], e["error"]) for e in read_log(db)] == [
        ("SELECT id FROM tickets WHERE severity = 'P1'", 1, None)
    ]


def test_run_query_logs_refused_and_failed_queries_too(db):
    for sql in ("UPDATE tickets SET status = 'closed'", "SELECT colour FROM tickets"):
        with pytest.raises(ToolError):
            run_query(sql, db)
    entries = read_log(db)
    assert [e["sql"] for e in entries] == [
        "UPDATE tickets SET status = 'closed'",
        "SELECT colour FROM tickets",
    ]
    assert all(e["rows"] == 0 and e["error"] for e in entries)
