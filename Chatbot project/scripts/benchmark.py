"""Benchmark the chatbot: 50 questions, one at a time, in one retrieval mode.

Run: .venv/Scripts/python.exe -m scripts.benchmark --mode vector
     .venv/Scripts/python.exe -m scripts.benchmark --mode rerank
Reports p50, p95 and the slowest whole answer, errors, average tokens and the estimated cost per question.
Prices come from INPUT_PRICE and OUTPUT_PRICE in .env (US dollars per million tokens).
Saves data/benchmark_<mode>.json and adds the numbers to data/eval_summary.json. Every call is also in logs/calls.jsonl.
"""
import argparse
import json
import os
import time

from dotenv import load_dotenv

from app.answer import answer
from app.benchmark import benchmark_questions, summarize_calls
from app.config import P95_TARGET_SECONDS, RETRIEVAL_MODES, ROOT, SELF_CRITIQUE
from app.eval_suite import split_turns, update_summary
from app.llm import reset_usage, usage_snapshot

PAUSE_PER_CALL = 3.0  # seconds after each model call, to stay under the hosted model's rate limit (not part of the timings)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=RETRIEVAL_MODES, required=True)
    parser.add_argument("--count", type=int, default=50)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    try:
        input_price, output_price = float(os.environ["INPUT_PRICE"]), float(os.environ["OUTPUT_PRICE"])
        critic_in, critic_out = float(os.getenv("JUDGE_INPUT_PRICE", "0")), float(os.getenv("JUDGE_OUTPUT_PRICE", "0"))
    except (KeyError, ValueError):
        print("ERROR: set INPUT_PRICE and OUTPUT_PRICE (dollars per million tokens) in .env.")
        return 1

    questions = benchmark_questions(args.count)
    key = args.mode + ("+critique" if SELF_CRITIQUE else "")
    print(f"Benchmark: {len(questions)} questions in {args.mode} mode, self-critique {'ON' if SELF_CRITIQUE else 'off'} "
          f"(prices ${input_price}/${output_price}; reviewer ${critic_in}/${critic_out} per million tokens)...", flush=True)
    rows = []
    for n, case in enumerate(questions, start=1):
        turns = split_turns(case["previous_turns"])
        reset_usage()
        row = {"id": case["id"], "seconds": None, "input_tokens": 0, "output_tokens": 0, "critic_input_tokens": 0, "critic_output_tokens": 0, "error": ""}
        try:
            result = answer(case["input"], previous_question=turns[-1] if turns else "", mode=args.mode)
            row["seconds"] = result["seconds"]
        except Exception as err:  # noqa: BLE001: an error is counted, never allowed to stop the benchmark
            row["error"] = type(err).__name__
        usage = usage_snapshot()
        row["input_tokens"], row["output_tokens"] = usage["input_tokens"], usage["output_tokens"]
        row["critic_input_tokens"], row["critic_output_tokens"] = usage["critic_input_tokens"], usage["critic_output_tokens"]
        rows.append(row)
        if n % 10 == 0:
            print(f"  {n} / {len(questions)} done", flush=True)
        if usage["calls"] + usage["critic_calls"]:
            time.sleep(PAUSE_PER_CALL * (usage["calls"] + usage["critic_calls"]))

    s = summarize_calls(rows, input_price, output_price, critic_in, critic_out)
    s.update(mode=args.mode, self_critique=SELF_CRITIQUE, p95_target_seconds=P95_TARGET_SECONDS, meets_p95_target=(s["p95_seconds"] is not None and s["p95_seconds"] <= P95_TARGET_SECONDS),
             input_price_per_million=input_price, output_price_per_million=output_price)
    (ROOT / "data" / f"benchmark_{key.replace('+', '_')}.json").write_text(json.dumps({"summary": s, "rows": rows}, indent=2), encoding="utf-8")
    update_summary({"performance": {key: s}})

    print(f"\nmode {key}: p50 {s['p50_seconds']} s | p95 {s['p95_seconds']} s | slowest {s['slowest_seconds']} s | errors {s['errors']}")
    print(f"tokens per question: {s['avg_input_tokens']} in, {s['avg_output_tokens']} out | cost about ${s['cost_per_question_usd']:.5f} per question (${s['cost_per_1000_usd']} per 1,000)")
    print(f"p95 target {P95_TARGET_SECONDS} s: {'MET' if s['meets_p95_target'] else 'MISSED'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
