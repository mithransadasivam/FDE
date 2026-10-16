"""Browser tests: start the Streamlit app on 127.0.0.1 (or use E2E_APP) and give tests its URL.

These tests talk to the real app, Ollama and the answer model, so they replace the unit tests'
no-network safety net (tests/conftest.py) with a version that does nothing.
"""
import os
import subprocess
import sys
import time
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PORT = 8599


@pytest.fixture(autouse=True)
def no_network_and_no_keys():
    """Override the unit-test fixture of the same name: browser tests need the network."""
    yield


@pytest.fixture(scope="session")
def app_url():
    external = os.getenv("E2E_APP")
    if external:
        yield external
        return
    env = {**os.environ, "COLLECTION_NAME": "my_docs", "DOCS_DIR": "data/my_docs"}
    server = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app/ui.py", "--server.address", "127.0.0.1",
         "--server.port", str(PORT), "--server.headless", "true", "--browser.gatherUsageStats", "false"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{PORT}"
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(url + "/_stcore/health", timeout=2)
                break
            except OSError:
                time.sleep(1)
        else:
            raise RuntimeError("The app did not start in 60 seconds.")
        yield url
    finally:
        server.terminate()
