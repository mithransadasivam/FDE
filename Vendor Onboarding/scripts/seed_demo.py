"""Fill the app with a realistic day: rebuild the database, run every request through the team, then act as a few people
so the Inbox shows every status (waiting for vendor, ready for approval, approver 1 of 2, created, rejected, stopped).

python -m scripts.seed_demo --llm live           (default; needs the key in .env)
python -m scripts.seed_demo --llm offline        (no API; for tests and CI only)
"""
import argparse
import shutil

from vendor_desk import config, db
from vendor_desk.casedesk import make_desk
from vendor_desk.evaluate import load_cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", choices=["live", "offline"], default="live")
    ap.add_argument("--tools", choices=["local", "mcp"], default="local")
    args = ap.parse_args()
    db.build_database()
    shutil.rmtree(config.RUNS_DIR / "team", ignore_errors=True)
    desk = make_desk(args.llm, args.tools)
    rows = [r for r in load_cases() if "-R" not in r["id"]]
    for row in rows:
        rid = row["request_file"].removesuffix(".txt")
        case = desk.submit(rid)
        print(f"{case['case_id']}: {case['status']:<20} {case['decision']}")
    desk.act("VOB-002", "approve", "alex@example.com", "Clean request; checked the evidence")      # -> CREATED
    desk.act("VOB-009", "approve", "alex@example.com", "Over £25,000, so a second approver is needed")  # approver 1 of 2
    desk.act("VOB-003", "reject", "sam@example.com", "Already a vendor as VEN-1001 (same tax ID)")      # -> REJECTED
    desk.close()
    print("Seeded the demo. Start the app with: streamlit run app.py")


if __name__ == "__main__":
    main()
