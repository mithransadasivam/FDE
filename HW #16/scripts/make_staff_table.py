"""Day 13: add the fictional staff directory to the help desk database, data/helpdesk.db.

python -m scripts.make_staff_table          (run python -m scripts.make_helpdesk_db first)

Three columns hold personal data that the MCP server must never return:
personal_mobile, home_address and date_of_birth.
"""

import csv
import sqlite3

DB = "data/helpdesk.db"
STAFF = "data/Day13_Slide05_staff.csv"
COLUMNS = [
    "username",
    "full_name",
    "department",
    "job_title",
    "manager",
    "work_email",
    "desk_extension",
    "office",
    "personal_mobile",
    "home_address",
    "date_of_birth",
]


def build(db=DB, staff=STAFF):
    with sqlite3.connect(db) as con:
        con.execute("DROP TABLE IF EXISTS staff")
        con.execute(
            "CREATE TABLE staff (username TEXT PRIMARY KEY, "
            + ", ".join(f"{c} TEXT" for c in COLUMNS[1:])
            + ")"
        )
        with open(staff, newline="", encoding="utf-8") as f:
            rows = [tuple(r[c] or None for c in COLUMNS) for r in csv.DictReader(f)]
        con.executemany(
            f"INSERT INTO staff VALUES ({','.join('?' * len(COLUMNS))})", rows
        )
        n = con.execute("SELECT COUNT(*) FROM staff").fetchone()[0]
    print(f"Added the staff table to {db}: {n} people")


if __name__ == "__main__":
    build()
