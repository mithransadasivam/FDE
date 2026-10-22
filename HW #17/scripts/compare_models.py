"""Day 16: the hosted model against a quantised open model you serve yourself, on the Day 6 test
questions: speed (time to the first word, whole answer, words per second), cost, and quality with
the Day 8 checks and judge.

python -m scripts.compare_models                          (LLM_MODEL against SMALL_MODEL)
python -m scripts.compare_models --no-judge               (code checks only)
python -m scripts.compare_models --models anthropic/claude-haiku-4.5 ollama/llama3.2:3b

Both models get exactly the same sources and prompt for each question. Saves the answers and the
summary in logs/model_comparison.json.
"""

import argparse
import csv
import json
import time
from pathlib import Path

from app import service
from app.perf import measure_stream, request_cost
from app.rag import DECLINE, MODEL, format_sources
from scripts.eval_answers import evaluate

QUESTIONS = "data/Day06_Slide25_test_questions.csv"


def run(model: str, questions: list[dict], found: dict) -> list[dict]:
    rows = []
    for i, q in enumerate(questions, 1):
        f = found[q["question"]]
        usage = {}
        if f["kept"]:
            start = time.perf_counter()
            m = measure_stream(
                service.open_stream(f["query"], f["kept"], model, usage), start
            )
        else:  # nothing relevant found: the chatbot declines without a model
            m = {"text": DECLINE, "first_token_seconds": None, "seconds": 0.0}
        text = m["text"].strip()
        pt, ct = usage.get("prompt_tokens"), usage.get("completion_tokens")
        writing = (
            (m["seconds"] - m["first_token_seconds"])
            if m["first_token_seconds"]
            else None
        )
        rows.append(
            {
                "id": i,
                "question": q["question"],
                "expected_answer": q["expected_answer"],
                "expected_behaviour": q["expected_behaviour"],
                "bot_answer": text,
                "declined": "yes" if text == DECLINE else "no",
                "sources": "; ".join(f["sources"]) if f["kept"] else "",
                "context": format_sources(f["kept"]) if f["kept"] else "",
                "human_correct": "",
                "human_grounded": "",
                "seconds": m["seconds"],
                "first_token_seconds": m["first_token_seconds"],
                "tokens_per_second": round(ct / writing, 1) if ct and writing else None,
                "cost_usd": request_cost(model if f["kept"] else None, pt, ct),
            }
        )
        print(f"  {model}: {i}/{len(questions)}", end="\r", flush=True)
    print()
    return rows


def summary_for(model: str, rows: list[dict], quality: dict) -> dict:
    answered = [r for r in rows if r["first_token_seconds"] is not None]
    avg = lambda key: (
        round(sum(r[key] for r in answered if r[key]) / len(answered), 2)
        if answered
        else None
    )
    return {
        "model": model,
        "first_token_seconds": avg("first_token_seconds"),
        "seconds": avg("seconds"),
        "tokens_per_second": avg("tokens_per_second"),
        "cost_per_1000": round(sum(r["cost_usd"] for r in rows) / len(rows) * 1000, 4),
        **{k: v for k, v in quality.items() if k.endswith("_rate")},
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--models", nargs="+", default=[MODEL, service.SMALL_MODEL])
    p.add_argument("--questions", default=QUESTIONS)
    p.add_argument("--no-judge", action="store_true")
    a = p.parse_args()
    with open(a.questions, newline="", encoding="utf-8") as f:
        questions = list(csv.DictReader(f))
    print("Finding the sources once for every question ...")
    found = {q["question"]: service.find(q["question"]) for q in questions}
    summaries, answers = [], {}
    for model in a.models:
        rows = run(model, questions, found)
        _, quality = evaluate(rows, use_judge=not a.no_judge)
        summaries.append(summary_for(model, rows, quality))
        answers[model] = rows
    keys = list(summaries[0])
    print(f"\n{'':22}" + "".join(f"{s['model'][-26:]:>28}" for s in summaries))
    for k in keys[1:]:
        print(f"{k:22}" + "".join(f"{s.get(k)!s:>28}" for s in summaries))
    out = Path("logs/model_comparison.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(
        json.dumps({"summary": summaries, "answers": answers}, indent=2),
        encoding="utf-8",
    )
    print(f"\nSaved {out}: read the answers side by side as well as the numbers.")


if __name__ == "__main__":
    main()
