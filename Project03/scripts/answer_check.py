"""Did /ask get worse after routing and the cache? Ten fixed questions, each with facts the answer must contain,
asked once with routing off and cache off (before) and once with routing on and cache on (after).

    python -m scripts.answer_check                # fake model
    python -m scripts.answer_check --model real   # real models
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from tower import db
from tower.llm import FakeLLM, OpenRouterLLM
from tower.settings import ROOT, Settings
from tower.tower import Tower

CHECKS = [  # (question, facts the answer must contain: all of them, case-insensitive)
    ("What is the status of the Payment Portal?", ["INC-3007", "P2"]),
    ("Which incidents are open right now?", ["INC-3003", "INC-3010"]),
    ("Who owns the Core Database?", ["Data Platform", "D. Osei"]),
    ("Which services depend on db-core?", ["payportal", "hr-selfservice", "ticketing-api"]),
    ("What does runbook RB-04 say to do first?", ["check_disk_usage"]),
    ("Which steps in RB-07 need approval?", ["clear_cache", "rollback_deploy"]),
    ("When does the change freeze start and end?", ["Friday 18:00", "Monday 06:00"]),
    ("What makes an incident P1?", ["tier-1", "three"]),
    ("Which team is on call for Identity?", ["R. Iyer"]),
    ("How do I fail over the core database?", ["failover_db", "RB-01"]),
]


def ask_all(model: str, routing: bool, cache: bool) -> list[tuple[str, str]]:
    tmp = Path(tempfile.mkdtemp(prefix="tower_qa_"))
    s = Settings.from_env().with_(db_path=tmp / "qa.db", actions_log=tmp / "a.log", app_log=tmp / "qa.log", routing=routing, cache=cache,
                                  model_mode="openrouter" if model == "real" else "fake", fake_latency_scale=0.0)
    db.build(s.db_path)
    llm = OpenRouterLLM(s) if model == "real" else FakeLLM(s, latency_scale=0.0)
    t = Tower(s, llm)
    t.triage()
    out = []
    for q, _ in CHECKS:
        r = t.ask(q)
        out.append((r.answer, r.route))
    shutil.rmtree(tmp, ignore_errors=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["fake", "real"], default="fake")
    model = ap.parse_args().model
    before, after = ask_all(model, False, False), ask_all(model, True, True)
    rows, tb, ta, worse = [], 0, 0, 0
    for (q, facts), (ba, _), (aa, route) in zip(CHECKS, before, after):
        norm = lambda s: s.lower().replace("_", " ")  # "check_disk_usage" and "check disk usage" are the same fact
        b = sum(norm(f) in norm(ba) for f in facts)
        a = sum(norm(f) in norm(aa) for f in facts)
        tb, ta, worse = tb + b, ta + a, worse + (a < b)
        rows.append({"q": q, "before": b, "after": a, "total": len(facts), "route": route})
    total = sum(r["total"] for r in rows)
    res = {"model": model, "rows": rows, "before": tb, "after": ta, "total": total, "worse": worse}
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "answer_check.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    for r in rows:
        print(f"{r['before']}/{r['total']} -> {r['after']}/{r['total']}  [{r['route']:5s}] {r['q']}")
    print(f"before {tb}/{total}  after {ta}/{total}  worse: {worse}")


if __name__ == "__main__":
    main()
