import csv
import sqlite3
from contextlib import closing

import pytest

from vendor_desk import config, db


def test_counts_match_the_seed_files(db):
    with closing(db_connect(db)) as con:
        c = db_counts(con)
    assert c["vendors"] == 20 and c["bank_accounts"] == 20 and c["watchlist"] == 12
    assert c["vendor_creations"] == 0


def db_connect(path):
    return sqlite3.connect(path)


def db_counts(con):
    from vendor_desk.db import counts
    return counts(con)


def test_rebuild_resets_everything(tmp_path):
    path = tmp_path / "x.db"
    db.build_database(path)
    with closing(sqlite3.connect(path)) as con:
        con.execute("DELETE FROM watchlist")
        con.commit()
    again = db.build_database(path)
    assert again["watchlist"] == 12


def test_near_duplicate_from_the_cases_is_really_in_the_data(db):
    """REQ-003 is Harrowgate Facilities Management; VEN-1001 is Harrowgate Facility Services with the same tax ID."""
    out = db_select(db, "SELECT vendor_id, tax_id FROM vendors WHERE name LIKE 'Harrowgate%'")
    assert out["rows"] == [["VEN-1001", "GB-TX-310442"]]
    out = db_select(db, "SELECT name FROM vendors WHERE name LIKE 'Corvane%'")
    assert out["rows"] == [["Corvane Print Solutions Ltd"]]


def db_select(path, sql):
    return db.run_select(sql, path)


def test_watchlist_entries_for_the_hard_cases_exist(db):
    out = db_select(db, "SELECT name FROM watchlist WHERE name LIKE 'Veltrix%' OR name LIKE 'Northern Meridian%'")
    assert {r[0] for r in out["rows"]} == {"Veltrix Marine Supplies Ltd", "Northern Meridian Trading Limited"}


def test_private_columns_are_refused_by_the_database_layer(db):
    for sql in ("SELECT account_number FROM bank_accounts", "SELECT * FROM bank_accounts",
                "SELECT sort_code FROM bank_accounts WHERE vendor_id='VEN-1001'",
                "SELECT vendor_id FROM bank_accounts WHERE account_number = '99310442'",
                "SELECT account_number FROM (SELECT * FROM bank_accounts)"):
        with pytest.raises(db_module().QueryRefused) as e:
            db_select(db, sql)
        assert "private" in str(e.value).lower()


def db_module():
    return db_mod


from vendor_desk import db as db_mod  # noqa: E402


def test_non_private_columns_still_work(db):
    out = db_select(db, "SELECT bank_country, COUNT(*) FROM bank_accounts GROUP BY bank_country ORDER BY 1")
    assert out["rows"][0][0] == "DE"
    out = db_select(db, "SELECT COUNT(*) FROM bank_accounts")
    assert out["rows"] == [[20]]


def test_only_a_single_select_is_allowed(db):
    for sql in ("DELETE FROM vendors", "SELECT 1; DROP TABLE vendors", "PRAGMA table_info(vendors)",
                "ATTACH DATABASE 'x.db' AS x"):
        with pytest.raises(db_mod.QueryRefused):
            db_select(db, sql)


def test_read_connection_cannot_write(db):
    with closing(db_mod.connect_readonly(db)) as con:
        with pytest.raises(sqlite3.DatabaseError):
            con.execute("INSERT INTO watchlist VALUES ('X','x','x','x')")


def test_create_vendor_record_is_idempotent(db):
    args = dict(case_id="VOB-099", name="Test Vendor Ltd", registered_country="GB", tax_id="GB-TX-000001",
                payment_terms_days=30, bank_name="Example Bank", bank_country="GB", account_number="99000001",
                sort_code="99-00-01", approvers=["a@example.com"], db_path=db)
    first = db_mod.create_vendor_record(**args)
    second = db_mod.create_vendor_record(**args)
    assert first["created"] and not second["created"] and first["vendor_id"] == second["vendor_id"] == "VEN-1021"
    assert db_select(db, "SELECT COUNT(*) FROM vendors")["rows"] == [[21]]
