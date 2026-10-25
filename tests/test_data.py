"""Phase 1: the database builds from the CSV files, the counts are right, and personal_mobile sits where no tool can reach it."""
import sqlite3

import pytest

from tower import db
from tower.rag import Index


def test_counts(tower):
    con = tower.con()
    assert db.counts_of(con) == {"services": 12, "oncall": 12, "alerts": 22, "past_incidents": 16}


def test_rebuild_resets(settings):
    db.build(settings.db_path)
    con = db.connect(settings.db_path)
    con.execute("DELETE FROM alerts")
    con.commit()
    con.close()
    assert db.build(settings.db_path)["alerts"] == 22


def test_personal_mobile_is_in_a_private_table(settings):
    db.build(settings.db_path)
    con = db.connect(settings.db_path)
    cols = [r[1] for r in con.execute("PRAGMA table_info(oncall)")]
    assert "personal_mobile" not in cols
    assert con.execute("SELECT COUNT(*) FROM oncall_private").fetchone()[0] == 12
    assert "oncall_private" in db.PRIVATE_TABLES


def test_the_application_connection_cannot_read_personal_mobile(tower):
    con = tower.con()
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("SELECT personal_mobile FROM oncall_private").fetchall()
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("SELECT * FROM oncall_private").fetchall()


def test_catalogue_and_index_never_contain_a_mobile(tower):
    import re
    blob = repr(tower.cat.oncall) + " ".join(c["text"] for c in Index(tower.cat).chunks)
    assert not re.search(r"7700\s?900\d{3}", blob)
    assert "personal_mobile" not in blob


def test_catalogue_loads_runbooks_and_policy(tower):
    assert len(tower.cat.runbooks) == 8
    assert tower.cat.runbooks["RB-07"].step(3).tool == "clear_cache"
    assert tower.cat.runbooks["RB-04"].step(3).needs_prerequisite
    assert "Friday 18:00" in tower.cat.clause("5.3")
    assert tower.cat.deps_closure("payportal") == {"db-core", "sso", "storage-san"}
