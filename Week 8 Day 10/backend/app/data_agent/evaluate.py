"""Evaluate the data agent on the bank's business questions, by running its queries (done, not a ticket).

Each question in data/Day07_Slide10_questions.json has the bank's own query (gold_sql) and its result (expected),
worked out with Deborah's MI team. A question is answered right when the agent's result holds the same values:
the same number of rows, and for every expected column a column with the same values (numbers to one decimal place,
text without regard to case). Column names and order do not matter, nor does extra columns.

Each question runs as the person who asked it, so row security is part of what is evaluated.
"""

import json
from collections import Counter
from datetime import datetime, timezone
from itertools import permutations

from app import store
from app.config import QUESTIONS_FILE_7, REPO
from app.data_agent import agent

DEFAULT_SETS = {"bank30": {"label": "The bank's 30 questions", "file": "data/Day07_Slide10_questions.json"}}

KINDS = {"term": "Ambiguous term", "period": "Time period", "join": "Join or double counting"}


def sets() -> dict:
    return {**DEFAULT_SETS, **store.load("data_agent/question_sets.json", {})}


def questions(set_name: str) -> list[dict]:
    s = sets().get(set_name)
    if not s:
        raise KeyError(f"No question set {set_name}")
    p = QUESTIONS_FILE_7 if set_name == "bank30" else REPO / s["file"]
    return json.loads(p.read_text(encoding="utf-8"))["questions"]


def _norm(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return round(float(v) + 1e-9, 1)
    s = str(v).strip().lower()
    try:
        return round(float(s) + 1e-9, 1)
    except ValueError:
        return s[:10] if len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-" else s


def same_result(expected: list[list], got: list[list]) -> bool:
    """True when `got` holds the expected values (see the module docstring)."""
    if len(expected) != len(got):
        return False
    if not expected:
        return True
    k, m = len(expected[0]), len(got[0]) if got else 0
    if m < k:
        return False
    want = Counter(tuple(_norm(v) for v in r) for r in expected)
    for cols in permutations(range(m), k):
        if Counter(tuple(_norm(r[c]) for c in cols) for r in got) == want:
            return True
    return False


def failure_kind(q: dict, a: dict) -> str:
    if a["status"] in ("refused", "error"):
        return "Refused or failed"
    if a["status"] == "cannot_answer":
        return "Said it cannot answer"
    for t in q.get("tags", []):
        if t.split(":")[0] in KINDS:
            return KINDS[t.split(":")[0]]
    return "Other"


def judge(q: dict, a: dict) -> bool:
    if q.get("expect_cannot_answer"):
        return a["status"] == "cannot_answer" or a["status"] == "refused"
    return a["status"] == "answered" and same_result(q["expected"]["rows"], a["rows"])


def run(set_name: str, layer: str, client, ids: list[str] | None = None) -> dict:
    """Ask every question (or only `ids`) and save engagement/data_agent/runs/<set>__<layer>.json."""
    results = []
    for q in questions(set_name):
        if ids and q["id"] not in ids:
            continue
        a = agent.ask(q["question"], q["user"], layer, client, qid=q["id"] if getattr(client, "is_fake", False) else "").model_dump()
        ok = judge(q, a)
        results.append({"id": q["id"], "question": q["question"], "user": q["user"], "tags": q.get("tags", []), "right": ok,
                        "failure": "" if ok else failure_kind(q, a), "expected": q.get("expected"), "answer": a,
                        "repaired": len(a["attempts"]) > 1 and a["status"] == "answered"})
    out = {"set": set_name, "layer": layer, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "model": getattr(client, "model", None), "results": results}
    store.save(f"data_agent/runs/{set_name}__{layer}.json", out)
    return out


def load_run(set_name: str, layer: str) -> dict | None:
    return store.load(f"data_agent/runs/{set_name}__{layer}.json", None)


def score(r: dict) -> dict:
    res = r["results"]
    n = len(res)
    right = sum(x["right"] for x in res)
    fails = Counter(x["failure"] for x in res if not x["right"])
    return {"set": r["set"], "layer": r["layer"], "at": r["at"], "questions": n, "right": right,
            "pct": round(100 * right / n, 1) if n else 0.0,
            "repaired": sum(x["repaired"] for x in res),
            "refused": sum(x["answer"]["status"] in ("refused", "error") for x in res),
            "failures": [{"kind": k, "count": c} for k, c in fails.most_common()],
            "tokens_in": round(sum(x["answer"]["tokens_in"] for x in res) / max(n, 1)),
            "tokens_out": round(sum(x["answer"]["tokens_out"] for x in res) / max(n, 1))}
