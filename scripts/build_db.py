"""Rebuild data/tower.db from the starter CSV files and print the counts. Run it again any time to reset.

    python -m scripts.build_db
"""
from tower import db
from tower.settings import Settings


def main() -> None:
    s = Settings.from_env()
    counts = db.build(s.db_path)
    print(f"built {s.db_path}")
    for table, n in counts.items():
        print(f"  {table:15s} {n}")


if __name__ == "__main__":
    main()
