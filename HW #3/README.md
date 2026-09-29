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
- Replies are capped with `max_tokens` (default 600, override with `BENCH_MAX_TOKENS`). Without a cap OpenRouter rejected the calls with HTTP 402 because the default limit (64,000 tokens) exceeded the account's credits.
- The local model ID must match `ollama list`: on this machine it is `llama3.2:3b`, not `llama3.2`.
- Status: 30 calls ran with no errors. The 1-5 scoring is not done yet.

## Task 3: cost report

- `scripts/cost_report.py` (run `python -m scripts.cost_report [path] [calls_per_day]`): reads `data/usage.csv` and prints per model the calls, input and output tokens, total cost and cost per call; the share of total cost from output tokens; and a monthly projection at 1,000 calls a day (30 days). Prices come from the registry in `.env`, the same ones `log_usage` used.
- `tests/test_cost_report.py` checks the maths on a small fixture CSV; no API calls.
- `HW #3/cost_report.txt` is the output on the real `data/usage.csv`: 9 calls (3 per backend, a 3-message chat each, made through `app.chatbot.ask`).
- Hand check: first row, haiku, 31 in x $1/1M + 202 out x $5/1M = $0.001041, equal to the logged cost.
- Fix found on the way: `ask()` sent no reply cap, so OpenRouter rejected calls with HTTP 402 when the account balance was low. It now sends `max_tokens` (`CHAT_MAX_TOKENS`, default 1000).

## Task 4: recommendation

- `HW #3/MODEL_CHOICE.md`: the five-section memo (recommendation, evidence, cost, risks, review), with every figure computed from `data/benchmark.csv`.
- `CLAUDE.md`: a "Model routing" section with the default and escalation rule.
- The 1-5 scores in `data/benchmark.csv` were assigned by Claude, not by a human reviewer. Review and change any you disagree with, then rerun the averages.
- The prompts are the ten course prompts, not prompts from my own work.
