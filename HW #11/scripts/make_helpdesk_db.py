"""Day 11: build the fictional help desk database, data/helpdesk.db, from the two CSV files.

python -m scripts.make_helpdesk_db            (run it again any time to reset every ticket)
"""

import csv
import sqlite3
from pathlib import Path

DB = "data/helpdesk.db"
TICKETS = "data/Day11_Slide05_tickets.csv"
ASSETS = "data/Day11_Slide05_assets.csv"


def build(db=DB, tickets=TICKETS, assets=ASSETS):
    Path(db).unlink(missing_ok=True)
    with sqlite3.connect(db) as con:
        con.execute("""CREATE TABLE tickets (id TEXT PRIMARY KEY, created TEXT, requester TEXT, application TEXT,
                       error_code TEXT, severity TEXT, status TEXT, assignee TEXT, summary TEXT, notes TEXT)""")
        con.execute("""CREATE TABLE assets (asset_tag TEXT PRIMARY KEY, device_type TEXT, model TEXT,
                       serial_number TEXT, assigned_to TEXT, department TEXT, purchase_date TEXT)""")
        with open(tickets, newline="", encoding="utf-8") as f:
            rows = [
                (
                    *[
                        r[k] or None
                        for k in (
                            "id",
                            "created",
                            "requester",
                            "application",
                            "error_code",
                            "severity",
                            "status",
                            "assignee",
                            "summary",
                        )
                    ],
                    "",
                )
                for r in csv.DictReader(f)
            ]
        con.executemany("INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
        with open(assets, newline="", encoding="utf-8") as f:
            con.executemany(
                "INSERT INTO assets VALUES (?,?,?,?,?,?,?)",
                [tuple(r.values()) for r in csv.DictReader(f)],
            )
        n_t = con.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        n_o = con.execute(
            "SELECT COUNT(*) FROM tickets WHERE status = 'open'"
        ).fetchone()[0]
        n_a = con.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    print(f"Built {db}: {n_t} tickets ({n_o} open), {n_a} assets")


if __name__ == "__main__":
    build()
