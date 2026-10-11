"""Browser-test harness: start the real Streamlit app on its own port, hand out its address, stop it afterwards.

Browser tests are named e2e_*.py so the quick `pytest tests` run does not collect them. Run them on their own:
    .venv/Scripts/python.exe -m scripts.browser_tests           (the fast ones: no real chatbot)
    .venv/Scripts/python.exe -m scripts.browser_tests --real    (also the journeys that use the real chatbot)

Four apps can run at once, each on its own port (never 8501 or 8502, the ones you use yourself):
    app_url                the real chatbot                     E2E_PORT           8611
    app_url_without_model  the real chatbot, answer model off   E2E_NO_MODEL_PORT  8612
    fake_app_url           the fake chatbot, quick              E2E_FAKE_PORT      8613
    slow_fake_app_url      the fake chatbot, words arrive slowly E2E_SLOW_PORT      8614
"""
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
E2E_PORT = int(os.getenv("E2E_PORT", "8611"))
NO_MODEL_PORT = int(os.getenv("E2E_NO_MODEL_PORT", "8612"))
FAKE_PORT = int(os.getenv("E2E_FAKE_PORT", "8613"))
SLOW_PORT = int(os.getenv("E2E_SLOW_PORT", "8614"))
STARTUP_SECONDS = 60


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _run_app(port: int, extra_env: dict | None = None):
    """Start the app on `port` with extra environment settings, wait until it is healthy, yield its address, stop it afterwards."""
    assert _port_is_free(port), f"Port {port} is already in use: stop whatever uses it or choose another port with the matching E2E_ variable."
    process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "ui.py"), "--server.port", str(port),
         "--server.address", "127.0.0.1", "--server.headless", "true"],
        cwd=ROOT, env=dict(os.environ, **(extra_env or {})), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + STARTUP_SECONDS
        while time.time() < deadline:
            try:
                urllib.request.urlopen(f"{url}/_stcore/health", timeout=2)
                break
            except OSError:
                time.sleep(0.5)
        else:
            pytest.fail(f"The app on port {port} did not start within {STARTUP_SECONDS} seconds.")
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


@pytest.fixture(scope="session")
def app_url():
    """The real app (real chatbot)."""
    yield from _run_app(E2E_PORT)


@pytest.fixture(scope="session")
def app_url_without_model():
    """The real app with its answer model switched off (an empty key is never overridden by .env). Needs Ollama, not OpenRouter."""
    yield from _run_app(NO_MODEL_PORT, {"OPENROUTER_API_KEY": ""})


@pytest.fixture(scope="session")
def fake_app_url():
    """The app with the FAKE chatbot: fixed topics, quick streaming, no models and no call log. It is started with an empty API key
    on purpose: nothing in a fake journey may depend on the hosted model."""
    yield from _run_app(FAKE_PORT, {"CHAT_FAKE": "1", "CHAT_FAKE_DELAY": "0.02", "CALL_LOG": "0", "OPENROUTER_API_KEY": ""})


@pytest.fixture(scope="session")
def slow_fake_app_url():
    """The fake chatbot with a long pause between words, for the streaming journey: the gap between the first word and the end is
    wide enough to check reliably."""
    yield from _run_app(SLOW_PORT, {"CHAT_FAKE": "1", "CHAT_FAKE_DELAY": "0.12", "CALL_LOG": "0", "OPENROUTER_API_KEY": ""})


@pytest.fixture(params=[pytest.param("fake", id="fake"), pytest.param("real", id="real", marks=pytest.mark.real)])
def chat_url(request):
    """The address of the fake app or of the real app: a journey that is about structure runs against both."""
    return request.getfixturevalue("fake_app_url" if request.param == "fake" else "app_url")


MULTIMODAL_PORT = int(os.getenv("E2E_MULTIMODAL_PORT", "8615"))


@pytest.fixture(scope="session")
def multimodal_app_url(tmp_path_factory):
    """The fake chatbot with fake vision, speech and picture models, pictures switched on, and its OWN empty knowledge-base folders, so a
    journey that uploads a scanned document never touches the real documents, the saved readings or the real index."""
    base = tmp_path_factory.mktemp("multimodal_kb")
    (base / "docs").mkdir()
    shutil.copy(ROOT / "data" / "docs" / "vpn_setup_guide.md", base / "docs")  # one ordinary document, so the question checks know some words
    env = {"CHAT_FAKE": "1", "CHAT_FAKE_DELAY": "0.02", "CALL_LOG": "0", "OPENROUTER_API_KEY": "", "ILLUSTRATIONS": "1",
           "KB_DOCS_DIR": str(base / "docs"), "KB_TRANSCRIPTS_DIR": str(base / "transcripts"), "KB_CHROMA_DIR": str(base / "chroma")}
    yield from _run_app(MULTIMODAL_PORT, env)
