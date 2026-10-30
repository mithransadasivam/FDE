"""Runs the attack test suite and prints its table (Day 3, prompt 2).

    python -m scripts.attack_report          # fake (gullible) models: proves the defences work, no key needed
    python -m scripts.attack_report --real   # the same attacks against the REAL model; needs OPENROUTER_API_KEY and FAKE_MODELS=0

The real-model run is the one that matters before you rely on the defences: the fakes are rule-based stand-ins. The table is also written to evidence/attack_results.json.
"""
import argparse
import os
import subprocess
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true", help="use the real model (needs an API key)")
    args = ap.parse_args()
    env = dict(os.environ)
    if args.real:
        if not env.get("OPENROUTER_API_KEY"):
            print("No OPENROUTER_API_KEY is set: the real-model run needs one. Run without --real for the fake-model run.")
            return 2
        env["FAKE_MODELS"] = "0"
        print("Running the attacks against the real model (this uses the API and costs a little) ...")
    else:
        env["FAKE_MODELS"] = "1"
    done = subprocess.run([sys.executable, "-m", "pytest", "tests/test_attacks.py", "-q", "-s", "-p", "no:cacheprovider"], env=env)
    write_dated_report(args.real, done.returncode == 0)
    return done.returncode


def write_dated_report(real: bool, tests_passed: bool) -> None:
    """The dated report the Trust and cost page and the governance pack read: reports/attack_report.json and .md (written by code, from evidence/attack_results.json)."""
    import json
    from pathlib import Path

    from evals.common import table, write_report

    p = Path("evidence/attack_results.json")
    if not p.exists():
        return
    every = json.loads(p.read_text(encoding="utf-8"))
    controls = [r for r in every if "WITHOUT" in r["attack"]]  # the defence removed on purpose: it must NOT be stopped, or the test proves nothing
    rows = [r for r in every if r not in controls]
    stopped = sum(1 for r in rows if r["result"] == "stopped")
    passed = tests_passed and stopped == len(rows) and all(c["result"] != "stopped" for c in controls)
    write_report("attack_report", "Attack tests (hidden and planted instructions)", {"mode": "real model" if real else "fake (gullible) models", "attacks": len(rows)},
                 {"stopped": stopped, "total": len(rows), "rows": rows, "controls": controls}, passed,
                 f"{stopped} of {len(rows)} attacks stopped.\n\n" + table(["attack", "where", "result"], [[r["attack"], r["where"], r["result"]] for r in rows]) +
                 "\n\nControl (the defence removed on purpose; it must get through, or the test proves nothing):\n\n" +
                 table(["attack", "where", "result"], [[r["attack"], r["where"], r["result"]] for r in controls]) +
                 "\n\nLimit: with fake models the attacks test the defences around the model (marking text as data, scanning, checking), not how a real model behaves. Run with --real before relying on them.")


if __name__ == "__main__":
    raise SystemExit(main())
