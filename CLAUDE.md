# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Coursework repo for an AI engineering course (GitHub: mithransadasivam/FDE). Homework write-ups live in `HW #1/` and `HW #2/` (folder names contain a space); shared code lives at the repo root. `HW #2/README.md` documents the homework 2 changes.

## Commands

Uses a `.venv` built on Python 3.13 (3.11 was requested but isn't installed on this machine). Run from the repo root:

```
.venv\Scripts\python -m pytest -q                        # all tests
.venv\Scripts\python -m pytest tests/test_llm_helper.py::test_returns_stripped_reply -q   # one test
.venv\Scripts\python -m ruff check .                     # lint
.venv\Scripts\python -m ruff format .                    # format
.venv\Scripts\python -m pip install -r requirements.txt  # deps (unpinned)
```

`app` is imported as a package from the repo root (`from app.llm_helper import ask_llm`), so run pytest from the root.

## Rules

- Never read, print or commit `.env` or any API key. Read keys with `os.getenv`.
- Every new function needs a pytest test, and `pytest -q` must pass before you say a task is done.
- Mock LLM calls in tests; never call a real API from a test.

## Architecture

- `app/llm_helper.py`: `ask_llm(prompt, model=None, temperature=0.2, client=None)` sends one user message through the `openai` library pointed at OpenRouter (`https://openrouter.ai/api/v1`) and returns the stripped reply.
  - `model` falls back to `LLM_MODEL` from `.env`; if neither is set it raises `RuntimeError`.
  - `OPENROUTER_API_KEY` is read only when no `client` is passed, so tests inject a fake client and never need a key.
  - It logs model, latency and total tokens at INFO, and the model at ERROR before re-raising on failure. It must never log the prompt, the reply or the key; tests assert this.
- `tools/log_parser.py`: `count_levels(lines)` counts INFO/WARNING/ERROR by the second whitespace-separated token and skips blank or short lines. It is tested by `tests/test_log_parser.py`.

## Testing notes

`tests/test_llm_helper.py` has an autouse fixture that stubs `load_dotenv` and clears `LLM_MODEL` and `OPENROUTER_API_KEY`, so tests don't depend on the real `.env`. New tests for `ask_llm` should use the `FakeClient` there rather than the network.

## Environment

- `.env` is gitignored and holds the real `OPENROUTER_API_KEY` and `LLM_MODEL`. `.env.example` is the committed template.
- The default model is a free OpenRouter model (`nvidia/nemotron-3.5-lightning:free`). Free models are often rate-limited upstream (HTTP 429), so a live call can fail for reasons unrelated to the code; try another `:free` model.
- `tests/`, `data/` and `notebooks/` were created with `.gitkeep` files so Git tracks them while empty.
