"""Starts the chat app for the browser tests, and stops it afterwards. Ready to use.

Each test file can say which app it tests with APP_FILE = "app/....py" at the top; otherwise the
Day 6 app (app/rag_app.py) is used, or the file in the E2E_APP setting. The app runs on port 8599,
so it does not clash with one you started yourself on 8501.

CHAT_FAKE=1 makes the streaming app use a fake chatbot: no Ollama and no API key needed (CI).
"""

import os
import subprocess
import sys
import time
import urllib.request

import pytest

PORT = 8599  # not 8501, so it never clashes with an app you started by hand


# One app server per test file (scope="module"): started before its first test, stopped after its last.
@pytest.fixture(scope="module")
def app_url(request):
    # Which app to run: APP_FILE in the test file, else the E2E_APP setting, else the full app.
    app_file = getattr(request.module, "APP_FILE", None) or os.getenv("E2E_APP", "app/ui.py")
    # Start Streamlit in the background with no browser window of its own.
    server = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", app_file, "--server.port", str(PORT),
         "--server.headless", "true", "--browser.gatherUsageStats", "false"],
        env={**os.environ, "COLLECTION_NAME": "my_docs", "DOCS_DIR": "data/my_docs"},  # my Day 7-8 data
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://localhost:{PORT}"
    for _ in range(60):  # wait up to 30 seconds for the app to start
        try:
            # Streamlit's health endpoint answers 200 once the app is ready.
            if urllib.request.urlopen(url + "/_stcore/health", timeout=1).status == 200:
                break
        except OSError:
            time.sleep(0.5)
    else:  # the loop never hit `break`: the app did not start in time
        server.terminate()
        pytest.fail(f"The app {app_file} did not start on {url}")
    yield url  # the tests run here
    server.terminate()  # clean-up: stop the app after the file's tests
    server.wait(timeout=10)
