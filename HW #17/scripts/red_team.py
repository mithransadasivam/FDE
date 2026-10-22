"""Day 17: run the red-team attacks and keep score.

python -m scripts.red_team --label before                          (no guardrails, the "wide" agent)
python -m scripts.red_team --label after --guardrails --profile least
python -m scripts.red_team --label check --only C04,A01            (just these attacks)
python -m scripts.red_team --label capstone --url http://localhost:8501/ask --attacks data/my_attacks.json

The chatbot runs in this process with your .env settings (CHAT_FAKE=1 for the fake, which falls for
every attack). The agent works on a copy of data/helpdesk.db, so an attack that works cannot
damage the real one. The report is saved in logs/red_team_<label>.json; compare two reports with
scripts/compare_red_team.py. Prompts are printed shortened, and nothing personal is printed.
"""

import argparse
import json
import os
import time
from pathlib import Path

from app.red_team import ATTACKS_FILE, load_attacks, run_attack, score_attack, summarise


def ask_url(url: str, prompt: str) -> dict:
    """--url: send the attack to any chatbot API that takes {"question": ...} and returns {"answer": ...}."""
    import httpx

    r = httpx.post(url, json={"question": prompt}, timeout=120)
    body = (
        r.json()
        if r.headers.get("content-type", "").startswith("application/json")
        else {}
    )
    return {
        "answer": body.get("answer", r.text if r.status_code == 200 else ""),
        "model": body.get("model", "unknown") if r.status_code == 200 else None,
        "blocked": bool(body.get("blocked")) or r.status_code != 200,
        "guardrail": body.get(
            "guardrail", [] if r.status_code == 200 else [f"HTTP {r.status_code}"]
        ),
        "calls": [],
        "notes": [],
    }


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--label", required=True)
    parser.add_argument(
        "--guardrails",
        action="store_true",
        help="turn the guardrails on (GUARDRAILS=1)",
    )
    parser.add_argument(
        "--profile", choices=["wide", "least"], default="wide", help="the agent's tools"
    )
    parser.add_argument("--target", choices=["chatbot", "agent", "all"], default="all")
    parser.add_argument("--only", help="comma-separated attack ids")
    parser.add_argument("--attacks", default=ATTACKS_FILE)
    parser.add_argument(
        "--url",
        help="attack a chatbot API instead (chatbot attacks without a planted document)",
    )
    args = parser.parse_args()

    os.environ["GUARDRAILS"] = "1" if args.guardrails else "0"
    os.environ["CACHE"] = "0"  # every attack must reach the chatbot, not a saved answer
    attacks = load_attacks(args.attacks)
    if args.target != "all":
        attacks = [a for a in attacks if a["target"] == args.target]
    if args.only:
        wanted = {x.strip() for x in args.only.split(",")}
        attacks = [a for a in attacks if a["id"] in wanted]
    if args.url:
        attacks = [
            a for a in attacks if a["target"] == "chatbot" and not a.get("planted")
        ]

    rows = []
    print(f"{'id':4} {'target':8} {'technique':46} result")
    for a in attacks:
        start = time.perf_counter()
        try:
            if args.url:
                result = ask_url(args.url, a["prompt"])
                result.update(score_attack(a, result))
            else:
                result = run_attack(a, profile=args.profile, guardrails=args.guardrails)
        except Exception as error:  # noqa: BLE001  (one failing attack must not stop the run)
            result = {
                "answer": "",
                "succeeded": False,
                "evidence": "",
                "blocked": False,
                "guardrail": [],
                "error": f"{type(error).__name__}: {error}",
            }
        row = {
            "id": a["id"],
            "target": a["target"],
            "owasp": a["owasp"],
            "technique": a["technique"],
            "succeeded": result["succeeded"],
            "evidence": result["evidence"],
            "blocked": result.get("blocked", False),
            "guardrail": result.get("guardrail", []),
            "error": result.get("error"),
            "answer": (result.get("answer") or "")[:300],
            "seconds": round(time.perf_counter() - start, 2),
        }
        rows.append(row)
        if row["error"]:
            outcome = "ERROR   " + row["error"][:60]
        elif row["succeeded"]:
            outcome = "WORKED  " + row["evidence"]
        else:
            outcome = "stopped " + (
                "; ".join(row["guardrail"])[:60] or "the model did not fall for it"
            )
        print(f"{a['id']:4} {a['target']:8} {a['technique'][:46]:46} {outcome}")

    summary = summarise(rows)
    print(
        f"\n{summary['succeeded']} of {summary['attacks']} attacks worked "
        f"(chatbot {summary['chatbot_success_rate']}, agent {summary['agent_success_rate']}); "
        f"{summary['blocked_by_guardrails']} blocked by a guardrail."
    )
    settings = {
        "guardrails": args.guardrails,
        "profile": args.profile,
        "fake": os.getenv("CHAT_FAKE") == "1",
        "url": args.url,
    }
    out = Path(f"logs/red_team_{args.label}.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "label": args.label,
                "settings": settings,
                "summary": summary,
                "results": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
