"""Run all 10 scenarios through the tower and score them against data/scenarios.csv.

    python -m scripts.run_scenarios                  # fake model, offline (also what the tests use)
    python -m scripts.run_scenarios --model real     # the real models through OpenRouter; spends a few cents
    python -m scripts.run_scenarios --model real --report   # also write EVAL_REPORT.md
"""
from __future__ import annotations

import argparse
import shutil
import tempfile
import time
from pathlib import Path

from tower import db
from tower.evaluate import ALL_CHECKS, CHECKS_RULES, score
from tower.llm import FakeLLM, OpenRouterLLM
from tower.settings import ROOT, Settings
from tower.tower import Tower


def run(model: str = "fake") -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="tower_eval_"))
    base = Settings.from_env()
    s = base.with_(db_path=tmp / "eval.db", actions_log=tmp / "actions.log", cache=False,
                   model_mode="openrouter" if model == "real" else "fake", fake_latency_scale=0.0)
    db.build(s.db_path)
    if model == "real":
        if not s.api_key:
            raise SystemExit("no OPENROUTER_API_KEY: cannot run the real model")
        llm = OpenRouterLLM(s)
    else:
        llm = FakeLLM(s, latency_scale=0.0)
    tower = Tower(s, llm)
    t0 = time.time()
    incidents = tower.triage()
    elapsed = time.time() - t0
    result = score(incidents)
    result["elapsed_s"] = round(elapsed, 1)
    result["metrics"] = tower.metrics.snapshot()
    result["model"] = {"mode": model, "large": llm.model_name("large"), "small": llm.model_name("small")}
    result["incidents"] = incidents
    shutil.rmtree(tmp, ignore_errors=True)
    return result


def write_report(res: dict, path: Path) -> None:
    s, m = res["summary"], res["metrics"]
    n = s["scenarios"]
    lines = [
        "# EVAL_REPORT: the 10 scenarios",
        "",
        f"Run: {time.strftime('%Y-%m-%d %H:%M')} · model mode: **{res['model']['mode']}** · large `{res['model']['large']}` · small `{res['model']['small']}`",
        f"· whole starter set triaged and briefed in **{res['elapsed_s']} s**.",
        "",
        "## Scorecard",
        "",
        "| Check | Result | Decided by |",
        "|---|---|---|",
    ]
    by = {"grouping": "rules", "root_cause": "rules", "severity": "rules", "approvals": "rules", "similar": "rules",
          "flags": "rules + guardrails", "status": "rules, then the model's check", "runbook_step": "model recommends, code checks"}
    for c in ALL_CHECKS:
        lines.append(f"| {c.replace('_', ' ')} | {s[c]}/{n} | {by[c]} |")
    lines += ["", f"Incidents produced: **{s['incident_count']}** (expected 10 from 22 alerts).", "",
              f"Model calls: {m['model_calls_total']} · tokens: {m['tokens_total']:,} · cost: ${m['cost_usd_total']:.4f} · "
              f"cost per incident brief: ${m['cost_per_incident_brief_usd']:.4f}", "",
              "## Scenario by scenario", "",
              "| Scenario | Incident | " + " | ".join(c.replace("_", " ") for c in ALL_CHECKS) + " |",
              "|---|---|" + "---|" * len(ALL_CHECKS)]
    for r in res["rows"]:
        lines.append(f"| {r['scenario']} | {r['incident']} | " + " | ".join("yes" if r.get(c) else "**NO**" for c in ALL_CHECKS) + " |")
    crew = [s for i in res["incidents"] for s in i.crew]
    planner = sum(1 for s in crew if s["agent"] == "Planner")
    vfail = sum(1 for s in crew if s["agent"] == "Verifier" and s["status"] == "fail")
    fallback = sum(1 for s in crew if s["agent"] == "Investigator" and s["status"] == "warn")
    reads = sum(1 for s in crew if s["kind"] == "tool")
    lines += ["", "## How the models behaved", "",
              f"- Planner attempts: **{planner}** for {sum(1 for i in res['incidents'] if i.brief or i.needs_person_reason and i.root_cause and i.status != 'AUTO_RESOLVED')} actionable incidents; "
              f"Verifier rejections: **{vfail}** (each is retried once, then the incident stops for a person).",
              f"- Investigator: **{reads}** [READ] tool calls; **{fallback}** time(s) the model's reply could not be used and the tower ran the runbook's [READ] steps in order instead.",
              f"- The planner model sees alert text only after hiding and the input check; flagged alert text is withheld entirely."]
    misses = [r for r in res["rows"] if not all(r.get(c) for c in ALL_CHECKS)]
    lines += ["", "## Misses", ""]
    if not misses:
        lines.append("None: every check passed on every scenario.")
    for r in misses:
        bad = [c for c in ALL_CHECKS if not r.get(c)]
        lines.append(f"- **{r['scenario']}** missed {', '.join(bad)}. Got `{r.get('got')}`, wanted `{r.get('want')}`.")
    lines += ["", "## How to read this", "",
              "- *grouping, root cause, severity, approvals, similar incident* are plain Python (`tower/triage.py`) and score the same with or without a model.",
              "- *runbook step* and *status* depend on the model: a recommendation that fails the code check is retried once, then the incident stops as NEEDS_PERSON.",
              "- `scripts/run_scenarios.py --model real --report` regenerates this file."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["fake", "real"], default="fake")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    res = run(a.model)
    s = res["summary"]
    print(f"model: {res['model']}  incidents: {s['incident_count']}  time: {res['elapsed_s']} s")
    for c in ALL_CHECKS:
        print(f"  {c:13s} {s[c]}/{s['scenarios']}")
    for r in res["rows"]:
        bad = [c for c in ALL_CHECKS if not r.get(c)]
        if bad:
            print(f"  MISS {r['scenario']}: {bad} got={r.get('got')}")
    if a.report:
        write_report(res, ROOT / "EVAL_REPORT.md")
        print("wrote EVAL_REPORT.md")


if __name__ == "__main__":
    main()
