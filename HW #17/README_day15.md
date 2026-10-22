# Day 15 · Student files

Copy everything in this folder into the root of your course repository, `ai-engineer-course/`, keeping the folder names. It includes files at the top level (`Dockerfile`, `.dockerignore`, `docker-compose.yml`, `requirements-api.txt`) and a hidden folder, `.github/workflows/`. `tests/conftest.py` replaces the Day 13 version (it adds one fixture); nothing else overwrites a file you edited on earlier days.

Then, through Claude Code (slide 5):

- install `fastapi`, `uvicorn[standard]`, `httpx`, `arize-phoenix-otel` and `openinference-instrumentation-openai`, and add them to requirements.txt;
- make `embedding_client()` in `app/embeddings.py` read Ollama's address from an `OLLAMA_URL` setting (default `http://localhost:11434/v1`), so the container can reach Ollama on your laptop;
- add `logs/requests.jsonl` to `.gitignore`.

You need Docker Desktop installed and running, the Day 10 index in `data/chroma` (`python -m scripts.build_index_vision`), Ollama running, and `OPENROUTER_API_KEY` in `.env`. No key, or a slow connection? Every activity also works with the fake chatbot: `CHAT_FAKE=1`.

## Lecture deck

| File | Slide | What it is for |
|---|---|---|
| `app/api.py` | 8, 9 | The FastAPI service: health, readiness, streaming, metrics and the pages (done). Activity 1: fill in `ask()` |
| `tests/test_api.py` | 9 | Tells you when Activity 1 is done: 5 tests |
| `app/service.py` | 9, 13, 14 | The chatbot as a service: sources, the model's stream, the fallback, the spans (done). Activity 2: fill in `readiness()` |
| `tests/test_readiness.py` | 14 | Tells you when Activity 2 is done: 5 tests |
| `Dockerfile`, `.dockerignore`, `requirements-api.txt` | 12, 14 | Builds the chatbot image. The index in `data/chroma` is copied in, so build the index first; `.env` is never copied |
| `docker-compose.yml` | 13, 14 | Starts the chatbot (port 8000) and Phoenix (port 6006). `SIMULATE_OUTAGE=primary` or `=all` makes models fail on purpose |
| `app/static/index.html`, `app/static/dashboard.html` | 9, 18 | The chat page (`/`) and the dashboard (`/dashboard`) (done) |
| `app/tracing.py` | 19, 20 | Sends spans to Phoenix when `TRACING=1` (done). Activity 3: fill in `trace_step()` |
| `tests/test_tracing.py` | 20 | Tells you when Activity 3 is done: 5 tests |
| `scripts/send_questions.py`, `data/Day15_Slide20_questions.csv` | 20, 25 | Sends ten class questions to the running service and prints each answer's time and model |
| `app/reliability.py` | 23, 25 | Retry settings and which errors are worth retrying (done). Activity 4: fill in `call_with_fallback()` |
| `tests/test_reliability.py` | 25 | Tells you when Activity 4 is done: 8 tests |
| `app/monitoring.py` | 18 | The request log and the dashboard numbers (done). Homework: `check_alerts()` |
| `tests/test_service_parts.py`, `tests/day15_helpers.py` | – | Tests for the finished parts (they pass from the start), and the `fake_chatbot` fixture |
| `tests/e2e/e2e_container.py` | 24 | Browser and API tests against the running container: `pytest tests/e2e/e2e_container.py` |
| `.github/workflows/container-check.yml` | 24 | On every push: build the image, start it with the fake chatbot, wait for /ready, run the container tests |
| `logs/Day15_Activity_Log.md` | All activities | Record your results; submit it with your homework |

## Homework deck

| File | Slide | What it is for |
|---|---|---|
| `tests/test_alerts.py` | 3 | Tells you when Task 1 (`check_alerts()`) is done: 5 tests |
| `data/Day15_HW_Slide03_alert_rules.json` | 3, 4 | The alert rules the dashboard checks: one example; add yours |
| `data/Day15_HW_Slide05_runbook_template.md` | 5 | The one-page runbook template |

Keep `.env`, `logs/requests.jsonl` and `outbox/` out of git and out of the image. Stop the containers at the end of the day with `docker compose down`.

All data is invented: no real company, people, systems or documents. The code files keep plain names because Python imports them by name.
