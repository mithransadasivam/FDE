"""Day 11: the provided tools work, and cannot be misused. Done: these pass from the start."""

import json
import sqlite3

import pytest

from app.tools import (
    calculate,
    find_tickets,
    get_ticket,
    search_policies,
    service_status,
    update_ticket,
)
from tests.day11_fakes import tiny_db


def test_calculate_does_arithmetic_but_never_runs_code():
    assert calculate("12 * 7.5 * 12")["result"] == 1080
    with pytest.raises(ValueError):
        calculate("__import__('os').getcwd()")


def test_service_status_knows_only_listed_services(tmp_path):
    f = tmp_path / "status.json"
    f.write_text(
        json.dumps({"Wi-Fi": {"status": "operational", "since": "", "note": ""}})
    )
    assert service_status("Wi-Fi", status_file=str(f))["status"] == "operational"
    with pytest.raises(ValueError):
        service_status("Payroll", status_file=str(f))


def test_find_tickets_filters_and_counts(tmp_path):
    db = tiny_db(tmp_path / "t.db")
    out = find_tickets(status="open", application="SecureLink VPN", db_path=db)
    assert out["count"] == 1 and out["tickets"][0]["id"] == "INC-0001"
    assert find_tickets(db_path=db, limit=1)["count"] == 3


def test_reading_tools_cannot_change_the_database(tmp_path):
    db = tiny_db(tmp_path / "t.db")
    find_tickets(
        status="open'; DELETE FROM tickets; --", db_path=db
    )  # treated as a value, not as SQL
    assert get_ticket("INC-0002", db_path=db)["status"] == "open"
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 3


def test_update_ticket_changes_status_and_keeps_a_note(tmp_path):
    db = tiny_db(tmp_path / "t.db")
    out = update_ticket("INC-0001", "closed", "User confirmed VPN works", db_path=db)
    assert out == {"id": "INC-0001", "old_status": "open", "new_status": "closed"}
    assert "User confirmed" in get_ticket("INC-0001", db_path=db)["notes"]
    assert search_policies("anything", retriever=lambda q: [])["found"] is False
