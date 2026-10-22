# Day 17 · Student files

Copy everything in this folder into the root of your course repository, `ai-engineer-course/`, keeping the folder names. Commit your Day 16 work first.

These files **replace** an earlier version: `app/service.py`, `app/api.py`, `app/static/index.html`, `Dockerfile`, `requirements-api.txt`, `docker-compose.yml`, `.github/workflows/container-check.yml` (a hidden folder), `tests/conftest.py` and `tests/test_service_parts_day16.py`. The new `service.py` and `api.py` contain the finished Day 16 code, so nothing you built stops working: with `GUARDRAILS` unset, the chatbot behaves exactly as on Day 16. Today's TODOs are in four new files.

Then, through Claude Code (slide 5):

- install `presidio-analyzer` and `presidio-anonymizer`, and add them to requirements.txt;
- download Presidio's language model: `python -m spacy download en_core_web_sm` (about 15 MB);
- run `pytest -q tests/test_service_parts_day17.py`: 10 tests pass.

The agent attacks need the staff table from Day 13 in `data/helpdesk.db` (if it is missing: `python -m scripts.make_staff_table`). The red team never changes `data/helpdesk.db`: the agent works on a copy. Set `CHAT_FAKE=1` in `.env` for the activities: the fake model falls for every attack on purpose, so each defence is easy to see. Run the attacks with the real model at the end, to see what the model resists by itself. Docker Desktop must be running for Activity 4.

Settings: `GUARDRAILS=1` turns on the checks on questions, documents and answers; `MAX_INPUT_CHARS` (2000) is the longest question; `ALLOWED_LINK_DOMAINS` (example.com) lists the domains an answer may link to; `JUDGE_MODEL` is the model for the output judge (default: the chatbot's model).

## Lecture deck

| File | Slide | What it is for |
|---|---|---|
| `data/Day17_Slide09_attacks.json` | 8, 9 | The 15 attacks: 9 on the chatbot, 6 on the Day 12 agent, each with its OWASP id and a success rule |
| `app/red_team.py` | 9 | Runs one attack and plants documents for the indirect ones (done). Activity 1: fill in `score_attack()` |
| `tests/test_red_team_score.py` | 9 | Tells you when Activity 1 is done: 7 tests |
| `scripts/red_team.py`, `scripts/compare_red_team.py` | 9, 14, 20, 25 | Run the attacks and save `logs/red_team_<label>.json`; put two reports side by side. `--url` attacks any chatbot API (homework) |
| `app/gullible_fake.py` | 5, 9 | A fake model that falls for every class attack when it sees the attack's text (done) |
| `app/guardrails.py` | 12, 13, 14, 19 | The patterns, the document check, the output check and the judge (done). Activity 2: fill in `check_input()`. Homework: `find_secrets()` |
| `tests/test_input_guardrail.py` | 14 | Tells you when Activity 2 is done: 7 tests |
| `app/pii.py` | 18, 20 | Presidio's analyzer with two recognisers of our own (done). Activity 3: fill in `redact()` |
| `tests/test_pii.py` | 20 | Tells you when Activity 3 is done: 5 tests |
| `app/permissions.py` | 23, 25 | The agent's tools: the "in a hurry" set and the permissions list (done). Activity 4: fill in `restrict_tools()` |
| `tests/test_permissions.py` | 25 | Tells you when Activity 4 is done: 6 tests |
| `tests/test_security_regression.py` | 24, 25 | Every attack, in this process: all work without defences, only the accepted C03 with them. Passes when all four activities are done |
| `tests/e2e/e2e_security.py` | 24, 25 | Playwright and API tests against the running container (`GUARDRAILS=1`): every direct attack blocked, ordinary questions still answered |
| `app/service.py`, `app/api.py`, `app/static/index.html` | 5, 19 | Replaced: Day 16 finished, plus the guardrails. With guardrails on, `/ask/stream` sends the checked answer in one piece |
| `Dockerfile`, `requirements-api.txt`, `docker-compose.yml`, `.github/workflows/container-check.yml` | 25 | Replaced: Presidio in the image, the `GUARDRAILS` setting, and CI runs the security tests on every push |
| `tests/test_service_parts_day17.py`, `tests/day17_helpers.py` | 5 | Tests for the finished parts (they pass from the start), and the `red_team_env` fixture |
| `logs/Day17_Activity_Log.md` | All activities | Record your results; submit it with your homework |

## Homework deck

| File | Slide | What it is for |
|---|---|---|
| `tests/test_secrets.py` | 3 | Tells you when Task 1 (`find_secrets()` in `app/guardrails.py`) is done: 4 tests |
| `data/Day17_HW_Slide04_my_attacks_template.json` | 4 | Five attack templates from the OWASP Top 10 for LLM Applications 2026: copy to `data/my_attacks.json` |
| `data/Day17_HW_Slide05_security_findings_template.md` | 5 | The findings report template: copy to `docs/SECURITY_FINDINGS.md` |

Keep `.env` and `logs/` out of git. Attack only your own projects. Stop the containers at the end of the day with `docker compose down`.

All data is invented: no real company, people, systems or documents. The phone numbers are in a range reserved for drama and testing. The code files keep plain names because Python imports them by name.
