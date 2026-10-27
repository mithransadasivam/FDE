"""The quality gate (Day 2 role D, extended on Days 3-4): runs every evaluation, writes EVAL_REPORT.md and the governance pack, and exits 1 if any
number on the quality bar misses its target. CI runs this after the tests.

    python -m scripts.quality_gate              (takes a few minutes: it reads 52 CVs, runs the red team, the cost run and the bias tests)
    python -m scripts.quality_gate --quick      (skips the slow red-team and cost runs and reuses their last evidence files)

Each evaluation runs in its own process against a temporary database, so it never touches your real data.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

STEPS = [
    ("CV extraction", ["scripts.eval_extraction", "--quiet"], False),
    ("Ranking and interview scoring", ["scripts.eval_quality"], False),
    ("Copilot", ["scripts.eval_copilot"], False),
    ("Bias tests", ["scripts.run_bias_tests"], False),
    ("Red team", ["scripts.run_red_team"], True),
    ("Cost and speed", ["scripts.run_perf"], True),
]


def isolated_env() -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="gate_"))
    env = dict(os.environ)
    env.update({"FAKE_MODELS": "1", "DATABASE_URL": f"sqlite:///{(tmp / 'g.db').as_posix()}", "OPS_DATABASE_URL": f"sqlite:///{(tmp / 'ops.db').as_posix()}",
                "STORAGE_DIR": str(tmp / "storage"), "SECRET_KEY": "gate-secret-not-real", "OPENROUTER_API_KEY": "", "PYTHONIOENCODING": "utf-8"})
    return env


def run(module_args: list[str], env: dict) -> tuple[int, str]:
    p = subprocess.run([sys.executable, "-m", *module_args], capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    quick = "--quick" in sys.argv
    env = isolated_env()
    Path("evidence").mkdir(exist_ok=True)
    codes = {}
    for name, args, slow in STEPS:
        if quick and slow and Path("evidence").exists():
            print(f"[skipped in --quick] {name}")
            continue
        code, out = run(args, env)
        codes[name] = code
        tail = [ln for ln in out.splitlines() if ln.strip() and "INFO" not in ln and "Warning" not in ln and "warn" not in ln.lower()][-4:]
        print(f"[{'ok' if code == 0 else 'FAIL'}] {name}")
        for ln in tail:
            print("      " + ln.strip()[:150])
    from scripts.reports import write_eval_report
    write_eval_report()
    for step in (["scripts.build_governance"], ["scripts.governance_check"]):
        code, out = run(step, env)
        codes[step[0]] = code
        print(f"[{'ok' if code == 0 else 'FAIL'}] {step[0].split('.')[-1]}: " + out.strip().splitlines()[-1][:120])
    # the gate itself: every quality-bar number must meet its target
    def load(n):
        p = Path("evidence") / n
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    checks = {
        "extraction >= 90%": (load("eval_extraction.json") or {}).get("passed"),
        "ranking top-5 overlap >= 4 of 5 (all roles)": (load("eval_ranking.json") or {}).get("passed"),
        "interview scoring >= 80%": (load("eval_interview.json") or {}).get("passed"),
        "copilot key points >= 80% and forbidden question within 3 s": (load("eval_copilot.json") or {}).get("passed"),
        "red team >= 18 of 20 stopped": (load("red_team.json") or {}).get("passed"),
        "bias, screening: no unexplained differences": (load("bias_screening.json") or {}).get("passed"),
        "bias, transcription: differences reported": (load("bias_accents.json") or {}).get("reported"),
        "voice p95 within 2.5 s": (load("perf.json") or {}).get("voice", {}).get("passed"),
        "governance check passes": (load("governance_check.json") or {}).get("passed"),
    }
    print("\nQuality gate")
    for k, v in checks.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    passed = all(checks.values())
    print("\nQUALITY GATE: " + ("PASS" if passed else "FAIL"))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
