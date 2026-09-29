# HW #3

Homework 3: choosing and proving a model. Code stays at the repo root (`app/`, `tests/`) because `app` is imported as a package; write-ups and results go in this folder.

## Task 1: model registry built from `.env`

- `app/chatbot.py`: `build_backends()` now reads `BACKENDS=hosted,strong,local` and, for each name, `NAME_BASE_URL`, `NAME_KEY_VAR`, `NAME_MODEL`, `NAME_IN_PRICE`, `NAME_OUT_PRICE`. Each backend is a `Backend(client, model, in_price, out_price)`. It still unpacks as `(client, model)`, so the existing `ask()` tests are unchanged.
- Third backend: `strong` = `anthropic/claude-sonnet-4.5` via OpenRouter, $3 in / $15 out per 1M tokens (prices from OpenRouter's model list, 2026-09-28). `hosted` = `anthropic/claude-haiku-4.5`, $1 / $5.
- `/models` prints each backend's name, model ID and prices. `log_usage` now prices each call from the registry instead of `INPUT_PRICE` / `OUTPUT_PRICE`.
- Also implemented the Day 3 TODOs: `ask()` in `app/chatbot.py` and `build_messages` / `call_cost` in `app/chat_once.py`.
- `tests/test_registry.py`: loads all three backends from environment variables, checks `/models` output and price lookup, with no network.
- `.env.example` has the new variables. Copy them into your own `.env`.
