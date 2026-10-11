"""Run the browser tests on their own (the quick `pytest tests` run never collects them).

Run: .venv/Scripts/python.exe -m scripts.browser_tests              (the fast ones: fake chatbot, no models)
     .venv/Scripts/python.exe -m scripts.browser_tests --real       (also the journeys that use the real chatbot)
     .venv/Scripts/python.exe -m scripts.browser_tests --slow       (also the judged tests; implies --real; costs a few cents)
     .venv/Scripts/python.exe -m scripts.browser_tests --no-index   (skip tests that need the built vector index: used by the CI fast job)
     .venv/Scripts/python.exe -m scripts.browser_tests --headed     (watch the browser; slowed down so you can follow it)
Extra words are passed to pytest, for example: -k smoke
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def marker_expression(real: bool, slow: bool, no_index: bool) -> str:
    """The pytest -m expression that leaves out what was not asked for. `slow` (judged tests) implies `real`."""
    left_out = (["slow"] if not slow else []) + (["real"] if not (real or slow) else []) + (["index"] if no_index else [])
    return " and ".join(f"not {name}" for name in left_out)


def main() -> int:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--real", action="store_true", help="include the journeys that use the real chatbot (needs Ollama and the answer model)")
    parser.add_argument("--slow", action="store_true", help="include the judged tests (real chatbot and the judge model); implies --real")
    parser.add_argument("--no-index", action="store_true", help="skip tests that need the built vector index")
    parser.add_argument("--headed", action="store_true", help="show the browser, slowed down")
    args, extra = parser.parse_known_args()

    files = sorted(str(p) for p in (ROOT / "tests" / "e2e").glob("e2e_*.py"))
    command = [sys.executable, "-m", "pytest", *files, "-q"]
    marker = marker_expression(args.real, args.slow, args.no_index)
    if marker:
        command += ["-m", marker]
    if args.headed:
        command += ["--headed", "--slowmo", "500"]
    return subprocess.call(command + extra, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
