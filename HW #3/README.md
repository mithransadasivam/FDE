# HW #3

Homework 3: choosing and proving a model. Code stays at the repo root (`app/`, `tests/`) because `app` is imported as a package; write-ups and results go in this folder.

## Task 1: model registry built from `.env`

- `app/chatbot.py`: `build_backends()` now reads `BACKENDS=hosted,strong,local` and, for each name, `NAME_BASE_URL`, `NAME_KEY_VAR`, `NAME_MODEL`, `NAME_IN_PRICE`, `NAME_OUT_PRICE`. Each backend is a `Backend(client, model, in_price, out_price)`. It still unpacks as `(client, model)`, so the existing `ask()` tests are unchanged.
- Third backend: `strong` = `anthropic/claude-sonnet-4.5` via OpenRouter, $3 in / $15 out per 1M tokens (prices from OpenRouter's model list, 2026-09-28). `hosted` = `anthropic/claude-haiku-4.5`, $1 / $5.
- `/models` prints each backend's name, model ID and prices. `log_usage` now prices each call from the registry instead of `INPUT_PRICE` / `OUTPUT_PRICE`.
- Also implemented the Day 3 TODOs: `ask()` in `app/chatbot.py` and `build_messages` / `call_cost` in `app/chat_once.py`.
- `tests/test_registry.py`: loads all three backends from environment variables, checks `/models` output and price lookup, with no network.
- `.env.example` has the new variables. Copy them into your own `.env`.

## Task 2: benchmark

- `scripts/benchmark.py` (run `python -m scripts.benchmark` from the repo root): sends each line of `data/prompts.txt` to every backend in the registry and writes `data/benchmark.csv` with prompt number, backend, model ID, seconds, input tokens, output tokens, cost, an empty `score` column and the answer. A failed call is recorded as `ERROR: ...` and the run continues. It prints per-backend calls, average seconds and total cost.
- `tests/test_benchmark.py` checks rows, cost, timing, error handling, the summary and the CSV header with fake clients; no API calls.
- `data/prompts.txt` currently holds the ten course prompts from `data/Day03_HW_Slide04_prompts_course.txt`.
- Status: the 30-call run and the 1-5 scoring are not done yet.
