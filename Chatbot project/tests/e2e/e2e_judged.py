"""Judged browser tests: the judge reads what is ON THE SCREEN.

For five questions that matter most to users, a test asks the question in the real app, waits for the finished answer, reads the
answer text from the page (without the sources row), and gives it to the judge model together with the expected answer and the
chunks the search finds for that question. The test passes only when the judge says the answer is correct, faithful to the chunks
and relevant. This is the one place where the WORDING of an answer is judged, and it is judged by a model, never by a string match.

These tests use the real chatbot, the embedding model and the judge model, so they are marked `slow`: they run only when asked
(`python -m scripts.browser_tests --slow`) and cost a few cents. One run's time and cost are written to data/browser_judged_run.json.

When the judge disagrees with the evaluation script for the same question I look at the JUDGE first: the script's checks are plain code
and repeatable, while a judge is another model. I read the judge's reason against the chunks by hand. If the page's answer differs from
what the script saw, the browser path is the first suspect instead.
"""
import csv
import json
import os
import time
from datetime import datetime, timezone

import pytest
from dotenv import load_dotenv
from playwright.sync_api import Page

from app.calllog import read_log
from app.config import MIN_SCORE, ROOT, TOP_K
from app.eval_suite import load_suite
from app.judge import judge_answer
from app.llm import call_critic, reset_usage, usage_snapshot
from app.retriever import search
from tests.e2e.helpers import answer_text, ask, open_app, wait_for_answer

pytestmark = [pytest.mark.slow, pytest.mark.real]

KEY_QUESTIONS = ["QUA-01", "QUA-03", "QUA-04", "QUA-06", "QUA-07"]  # MFA, VPN dropping, password reset, swollen battery, P1 targets
CASES = {c["id"]: c for c in load_suite()}
RESULTS: list[dict] = []
STARTED = datetime.now(timezone.utc)


@pytest.fixture(scope="module", autouse=True)
def write_the_run_notes():
    load_dotenv(ROOT / ".env")
    reset_usage()
    started = time.time()
    yield
    judge_tokens = usage_snapshot()
    app_calls = [r for r in read_log() if r.get("time", "") >= STARTED.isoformat(timespec="seconds") and r.get("mode") != "fake"]
    price = lambda name: float(os.getenv(name, "0"))
    app_cost = sum(r.get("input_tokens", 0) * price("INPUT_PRICE") + r.get("output_tokens", 0) * price("OUTPUT_PRICE") for r in app_calls) / 1e6
    judge_cost = (judge_tokens["critic_input_tokens"] * price("JUDGE_INPUT_PRICE") + judge_tokens["critic_output_tokens"] * price("JUDGE_OUTPUT_PRICE")) / 1e6
    notes = {"questions": len(RESULTS), "passed": sum(1 for r in RESULTS if r["passed"]), "seconds": round(time.time() - started, 1),
             "answer_model_cost_usd": round(app_cost, 5), "judge_cost_usd": round(judge_cost, 5), "total_cost_usd": round(app_cost + judge_cost, 5),
             "cases": RESULTS}
    (ROOT / "data" / "browser_judged_run.json").write_text(json.dumps(notes, indent=2, ensure_ascii=False), encoding="utf-8")


def script_verdict(case_id: str) -> str:
    """What the evaluation script's judge said about the same question last time (correct / faithful), for the disagreement note."""
    try:
        with open(ROOT / "data" / "eval_judged.csv", newline="", encoding="utf-8") as f:
            row = next(r for r in csv.DictReader(f) if r["id"] == case_id)
        return f"correct={row['correct']} faithful={row['faithfulness']}"
    except (OSError, StopIteration):
        return "not judged"


@pytest.mark.parametrize("case_id", KEY_QUESTIONS)
def test_the_judge_approves_the_answer_shown_on_the_page(page: Page, app_url: str, case_id: str):
    case = CASES[case_id]
    open_app(page, app_url)
    ask(page, case["input"])
    wait_for_answer(page, 1)
    shown = answer_text(page, 1)  # the answer text only: the sources row is a separate element
    chunks = [c for c in search(case["input"], TOP_K) if c["score"] >= MIN_SCORE]
    scores = judge_answer(case["input"], shown, chunks, case["expected_answer"], call_critic)
    passed = bool(scores["correct"]) and bool(scores["faithfulness"]) and bool(scores["answer_relevance"])
    RESULTS.append({"id": case_id, "passed": passed, "scores": scores, "answer_on_page": shown, "script_judge_said": script_verdict(case_id)})
    assert passed, f"{case_id}: the judge did not approve the answer shown on the page: {scores['reason']} | scores: {scores} | answer: {shown!r}"
