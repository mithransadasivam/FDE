"""Build the pilot's Lambda package: infra/build/lambda.zip. Run from backend/:

    python -m scripts.build_lambda

Build the screens first (cd frontend && npm run build). The packages are downloaded for Lambda's Linux and
Python 3.12, whatever your own computer runs, so the zip works in AWS even when built on Windows or a Mac.
"""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUILD = REPO / "infra" / "build"
PKG = BUILD / "lambda"
ZIP = BUILD / "lambda.zip"
SKIP = shutil.ignore_patterns("__pycache__", "*.pyc", "tests", "node_modules", ".pytest_cache")
ENTRY = '''"""Lambda's entry point: the console's code is in backend/, laid out as in the repository."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from app.lambda_handler import handler  # noqa: E402,F401
'''


def main() -> None:
    dist = REPO / "frontend" / "dist"
    if not (dist / "index.html").exists():
        sys.exit("No frontend/dist: build the screens first (cd frontend && npm run build)")
    shutil.rmtree(BUILD, ignore_errors=True)
    PKG.mkdir(parents=True)
    print("Downloading packages for Lambda (Linux x86_64, Python 3.12)...")
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "-r", str(REPO / "backend" / "requirements-lambda.txt"),
                    "--platform", "manylinux2014_x86_64", "--implementation", "cp", "--python-version", "3.12",
                    "--only-binary=:all:", "--target", str(PKG)], check=True)
    shutil.copytree(REPO / "backend" / "app", PKG / "backend" / "app", ignore=SKIP)
    for folder in ("data", "docs", "evals", "engagement", "infra/guardrails"):
        if (REPO / folder).exists():
            shutil.copytree(REPO / folder, PKG / folder, ignore=SKIP)
    shutil.copytree(dist, PKG / "static")
    (PKG / "lambda_entry.py").write_text(ENTRY, encoding="utf-8")
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(PKG.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(PKG))
    mb = ZIP.stat().st_size / 1e6
    print(f"Built {ZIP.relative_to(REPO)}: {mb:.1f} MB")
    if mb > 50:
        print("Warning: Lambda takes at most 50 MB uploaded directly. Remove large files from data/ or engagement/.")


if __name__ == "__main__":
    main()
