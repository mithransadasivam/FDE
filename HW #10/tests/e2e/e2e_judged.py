"""Day 9, Activity 4: a judge model checks an answer inside a browser test.

Run it with:  pytest tests/e2e/e2e_judged.py
It needs the real models (Ollama, OpenRouter and JUDGE_MODEL), so it is not part of the CI run
on every push: run it before a release, or in the nightly CI job.
"""

from playwright.sync_api import Page, expect  # noqa: F401  (you will need it)

from app.judge import judge_answer  # noqa: F401  (you will need it)
from app.rag import format_sources  # noqa: F401  (you will need it)
from app.streaming import find_sources  # noqa: F401  (you will need it)
from tests.e2e.helpers import SOURCES, TIMEOUT, ask, last_answer_text  # noqa: F401  (you will need it)

APP_FILE = "app/rag_app_stream.py"

QUESTION = "How long can a VPN session stay connected?"
EXPECTED = "12 hours, then you must sign in again with MFA."


def test_the_vpn_answer_is_correct_and_grounded(page: Page, app_url: str):
    """TODO (Activity 4): ask in the browser, then let the judge read what the user saw.

    - ask(page, app_url, QUESTION), then expect the SOURCES line to be visible (timeout=TIMEOUT):
      the answer has finished streaming
    - shown = last_answer_text(page)
    - sources = format_sources(find_sources(QUESTION)["kept"]): the text the bot answered from
    - verdict = judge_answer(QUESTION, EXPECTED, shown, sources)
    - assert that verdict["correct"] and verdict["grounded"] are both true; use verdict["reason"]
      as the assertion message, so a failure says why
    """
    raise NotImplementedError("TODO")
