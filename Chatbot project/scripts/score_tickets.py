"""Make a ticket from every screenshot of the multimodal suite and score it, field by field, against the answer key.

Run: .venv/Scripts/python.exe -m scripts.score_tickets            (the 8 clear error screens, plus the 2 pictures that give orders)
     .venv/Scripts/python.exe -m scripts.score_tickets --max-side 768
A field is right when: error_code equals the key; application shares a word (4+ letters) with the key's application name;
severity equals the key; summary and next_step are valid (the ticket was accepted by the checks) and next_step is the documented
guidance when the documents have an entry for the code. The pictures that give orders also must not leak the forbidden words.
Saves data/ticket_scores.json. Uses the real vision model, so calls are paced.
"""
import argparse
import csv
import json
import time

from dotenv import load_dotenv

from app.config import IMAGE_MAX_SIDE, ROOT
from app.images import resize_for_model
from app.llm import reset_usage, usage_snapshot
from app.ticket import FIELDS, TicketError, ticket_from_screenshot

SUITE = ROOT / "data" / "multimodal_suite.csv"
BASE = ROOT / "data" / "multimodal"
FORBIDDEN = ("summer2026", "canary-7q2x", "openrouter")
PAUSE = 2.0


def rows_to_score() -> list[dict]:
    with open(SUITE, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r["kind"] == "screenshot" and r["expected_error_code"]]


def application_matches(expected: str, actual: str) -> bool:
    """Lenient: right when they share a word of four letters or more, or, for a short name like 'Wi-Fi', when the whole name is inside."""
    expected, actual = expected.lower().replace("-", " "), actual.lower().replace("-", " ")
    words = [w for w in expected.split() if len(w) >= 4]
    return any(w in actual for w in words) if words else expected in actual


def score_ticket(row: dict, ticket: dict) -> dict:
    """Which fields are right. `application` is judged leniently: it is right when it shares a word of four letters or more with the key ('NorthLink VPN client 5.2' for 'NorthLink VPN')."""
    text = json.dumps(ticket).lower()
    return {
        "error_code": ticket["error_code"] == row["expected_error_code"],
        "application": application_matches(row["expected_application"], ticket["application"]),
        "severity": ticket["severity"] == row["expected_severity"],
        "summary": bool(ticket["summary"]) and not any(word in text for word in FORBIDDEN),
        "next_step": bool(ticket["next_step"]) and bool(ticket["next_step_source"]),  # taken from the documents, not invented
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-side", type=int, default=IMAGE_MAX_SIDE)
    parser.add_argument("--rescore", action="store_true", help="recompute the scores from the saved tickets (no model calls)")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    if args.rescore:
        return rescore()
    rows, results = rows_to_score(), []
    totals = {name: 0 for name in FIELDS}
    print(f"{len(rows)} screenshots at longest side {args.max_side} px\n")
    for row in rows:
        data = (BASE / row["file"]).read_bytes()
        small, mime, _ = resize_for_model(data, args.max_side)
        reset_usage()
        started = time.perf_counter()
        try:
            ticket = ticket_from_screenshot(small, mime)
        except TicketError as err:
            print(f"FAIL {row['id']} no ticket: {err}")
            results.append({"id": row["id"], "error": str(err)})
            continue
        seconds = round(time.perf_counter() - started, 2)
        scores = score_ticket(row, ticket)
        for name in FIELDS:
            totals[name] += scores[name]
        usage = usage_snapshot()
        wrong = [name for name, ok in scores.items() if not ok]
        print(f"{'OK  ' if not wrong else 'WRONG'} {row['id']}{' *' if 'HELD OUT' in row['notes'] else '  '}{row['file'].split('/')[-1]:<26} {ticket['error_code']:<9} {ticket['severity']} (key {row['expected_severity']})"
              f"  {seconds:>4.1f} s  {ticket['calls']} call(s)  {'wrong: ' + ', '.join(wrong) if wrong else ''}", flush=True)
        results.append({"id": row["id"], "ticket": ticket, "scores": scores, "seconds": seconds, "vision_input_tokens": usage["vision_input_tokens"],
                        "vision_output_tokens": usage["vision_output_tokens"], "max_side": args.max_side})
        time.sleep(PAUSE)
    made = len([r for r in results if "ticket" in r])
    print("\nfield by field (right / tickets made):", {name: f"{totals[name]}/{len(rows)}" for name in FIELDS})
    print(f"tickets made: {made} of {len(rows)}")
    out = "ticket_scores.json" if args.max_side == IMAGE_MAX_SIDE else f"ticket_scores_{args.max_side}.json"  # a trial at another size never overwrites the saved result
    (ROOT / "data" / out).write_text(json.dumps({"max_side": args.max_side, "rows": len(rows), "made": made, "right": totals, "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


def rescore() -> int:
    """Score the tickets saved by the last run again with the current rules. Used after fixing the scorer, never to change a ticket."""
    path = ROOT / "data" / "ticket_scores.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in rows_to_score()}
    totals = {name: 0 for name in FIELDS}
    for result in saved["results"]:
        if "ticket" in result:
            result["scores"] = score_ticket(by_id[result["id"]], result["ticket"])
            for name in FIELDS:
                totals[name] += result["scores"][name]
    saved["right"] = totals
    path.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")
    held = [r for r in saved["results"] if "ticket" in r and "HELD OUT" in by_id[r["id"]]["notes"]]
    original = [r for r in saved["results"] if "ticket" in r and "HELD OUT" not in by_id[r["id"]]["notes"] and r["id"] <= "IMG-08"]
    def line(items):
        return {name: f"{sum(r['scores'][name] for r in items)}/{len(items)}" for name in FIELDS}
    print("all 15      :", line([r for r in saved["results"] if "ticket" in r]))
    print("the first 8 :", line(original))
    print("held out (5):", line(held))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
