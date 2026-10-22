# Day 16 · Student files

Copy everything in this folder into the root of your course repository, `ai-engineer-course/`, keeping the folder names. These files **replace** a Day 15 version: `app/service.py`, `app/api.py`, `app/static/dashboard.html`, `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `tests/conftest.py` and `tests/test_service_pipeline_day15.py`. The new `service.py` and `api.py` contain the finished Day 15 code, so nothing you built stops working; today's TODOs are in three new files. Commit your Day 15 work first.

Then, through Claude Code (slide 5):

- pull the open model in the background: `ollama pull llama3.2:3b` (about 2 GB, so start it now);
- add `cache/` and `logs/load_*.json` to `.gitignore`;
- rebuild and start the containers: `docker compose up -d --build`, then check `GET /ready`.

You need the Day 15 setup: Docker Desktop running, the Day 10 index in `data/chroma`, Ollama running, and `OPENROUTER_API_KEY` in `.env`. No key, or a slow connection? Every activity also works with the fake chatbot: `CHAT_FAKE=1` (its models cost nothing, so the costs show as 0).

Settings, all off or at their defaults unless you set them: `CACHE=1` turns the response cache on, `ROUTING=1` sends simple questions to `SMALL_MODEL` (default `ollama/llama3.2:3b`), `MAX_TOKENS` (400) caps an answer's length, `SIMULATE_OUTAGE=small` makes the small model fail on purpose.

## Lecture deck

| File | Slide | What it is for |
|---|---|---|
| `app/perf.py` | 7, 9, 20 | Prices, token estimates and the extra dashboard numbers (done). Activity 1: fill in `request_cost()`. Activity 3: fill in `measure_stream()` |
| `tests/test_costs.py` | 9 | Tells you when Activity 1 is done: 5 tests |
| `scripts/load_test.py`, `data/Day16_Slide09_load_questions.csv` | 8, 9, 14, 25 | Plays four users sending 60 questions; saves `logs/load_<label>.json` with p50, p95, throughput, cost per 1,000 and the cache hit rate |
| `scripts/compare_reports.py` | 14, 25 | Puts two or more load test reports side by side |
| `app/cache.py` | 13, 14 | The response cache: key, save, clear (done). Activity 2: fill in `ResponseCache.get()` |
| `tests/test_cache.py` | 14 | Tells you when Activity 2 is done: 5 tests |
| `tests/test_measure_stream.py` | 20 | Tells you when Activity 3 is done: 5 tests |
| `scripts/compare_models.py` | 20 | The hosted model against `llama3.2:3b` on the same questions and sources: time to first token, tokens per second, cost and quality. Writes `logs/model_comparison.json` |
| `app/router.py` | 23, 25 | Which questions are simple. Activity 4: fill in `choose_route()` |
| `tests/test_router.py` | 25 | Tells you when Activity 4 is done: 7 tests |
| `scripts/quality_recheck.py` | 24, 25 | Runs the Day 6 questions through the chatbot and checks them against the Day 8 thresholds: PASS or FAIL |
| `app/service.py`, `app/api.py`, `app/static/dashboard.html` | 5, 14, 25 | Replaced: Day 15 finished, plus the cache, routes, tokens and cost on every answer, `POST /cache/clear`, and new dashboard tiles (done) |
| `Dockerfile`, `.dockerignore`, `docker-compose.yml` | 5 | Replaced: the new settings and a `cache/` folder kept between restarts |
| `tests/test_service_parts_day16.py`, `tests/day16_helpers.py` | – | Tests for the finished parts (they pass from the start), and the `fresh_cache` fixture |
| `logs/Day16_Activity_Log.md` | All activities | Record your results; submit it with your homework |

## Homework deck

| File | Slide | What it is for |
|---|---|---|
| `tests/test_monthly_cost.py` | 3 | Tells you when Task 1 (`monthly_cost()` in `app/perf.py`) is done: 4 tests |
| `data/Day16_HW_Slide04_cost_report_template.md` | 4 | The cost report template: copy it to `docs/COST_REPORT.md` |
| `scripts/semantic_cache_trial.py`, `data/Day16_HW_Slide05_question_pairs.csv` | 5 | Similarity scores for twelve question pairs, and right and wrong hits at each threshold |

Keep `.env`, `cache/`, `logs/` and `outbox/` out of git and out of the image. Stop the containers at the end of the day with `docker compose down`.

All data is invented: no real company, people, systems or documents. Prices are illustrative: check OpenRouter's on the day. The code files keep plain names because Python imports them by name.
