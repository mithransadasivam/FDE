"""Day 17 homework, Task 3: ask ordinary questions with the guardrails on; count the false alarms.

python -m scripts.hw17_ordinary --url http://localhost:8000/ask --label after
Saves logs/hw17_ordinary_<label>.json. A question is "wrongly stopped" if the API says blocked.
"""

import argparse
import json

import httpx

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://localhost:8000/ask")
ap.add_argument("--label", default="after")
ap.add_argument("--questions", default="data/hw17_ordinary_questions.json")
args = ap.parse_args()

rows = []
for q in json.load(open(args.questions, encoding="utf-8")):
    r = httpx.post(args.url, json={"question": q}, timeout=180).json()
    row = {
        "question": q,
        "blocked": bool(r.get("blocked")),
        "declined": bool(r.get("declined")),
        "guardrail": r.get("guardrail", []),
        "answer": r.get("answer", "")[:200],
    }
    rows.append(row)
    flag = "BLOCKED " if row["blocked"] else ("declined" if row["declined"] else "answered")
    print(f"{flag} {q[:70]}  {'; '.join(row['guardrail'])[:60]}")
print(f"\n{sum(r['blocked'] for r in rows)} of {len(rows)} ordinary questions wrongly stopped")
json.dump(rows, open(f"logs/hw17_ordinary_{args.label}.json", "w", encoding="utf-8"), indent=2)
