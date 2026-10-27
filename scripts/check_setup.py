"""Prints OK or FIX (with the fix) for everything the project needs.  Run: python -m scripts.check_setup"""
import importlib
import shutil
import sys
from pathlib import Path

from app.config import get_settings

PACKAGES = {
    "fastapi": "fastapi", "uvicorn": "uvicorn", "jinja2": "jinja2", "python-multipart": "multipart",
    "itsdangerous": "itsdangerous", "sqlalchemy": "sqlalchemy", "pydantic": "pydantic",
    "pydantic-settings": "pydantic_settings", "bcrypt": "bcrypt", "litellm": "litellm",
    "faster-whisper": "faster_whisper", "pdfplumber": "pdfplumber", "python-docx": "docx",
    "pytesseract": "pytesseract", "pillow": "PIL", "pytest": "pytest", "httpx": "httpx",
}
failures = 0


def check(label: str, ok: bool, fix: str) -> None:
    global failures
    if ok:
        print(f"OK   {label}")
    else:
        failures += 1
        print(f"FIX  {label}: {fix}")


def main() -> int:
    s = get_settings()
    check("Python 3.11 or newer", sys.version_info >= (3, 11), "install Python 3.11+ and recreate .venv")
    check("ffmpeg (needed to read audio)", shutil.which("ffmpeg") is not None,
          "install ffmpeg and add it to PATH (Windows: download from gyan.dev, add its bin folder to PATH)")
    check("tesseract (fallback for scanned CVs)", shutil.which("tesseract") is not None,
          "install tesseract (Windows: UB-Mannheim installer) and add it to PATH")
    check(".env present", Path(".env").exists(), "copy .env.example to .env")
    check("SECRET_KEY changed", s.secret_key not in ("", "change-me", "change-me-to-a-long-random-text"),
          "set SECRET_KEY in .env to any long random text")
    check("model key or fake mode", bool(s.openrouter_api_key) or s.fake_models,
          "set OPENROUTER_API_KEY, or FAKE_MODELS=1")
    for pip_name, module in PACKAGES.items():
        try:
            importlib.import_module(module)
            ok = True
        except Exception:
            ok = False
        check(f"package {pip_name}", ok, f"pip install {pip_name}")
    print("\nAll good." if not failures else f"\n{failures} thing(s) to fix.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
