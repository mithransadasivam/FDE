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
    return done.returncode


if __name__ == "__main__":
    raise SystemExit(main())
