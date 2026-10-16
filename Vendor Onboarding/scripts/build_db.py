"""Build data/procurement.db from the seed files (run again any time to reset).

python -m scripts.build_db
"""
from vendor_desk import config, db


def main():
    result = db.build_database()
    print(f"Built {config.db_path()}")
    for table, n in result.items():
        print(f"  {table}: {n}")
    print("Private columns (never shown to a model): bank_accounts.account_number, bank_accounts.sort_code")


if __name__ == "__main__":
    main()
