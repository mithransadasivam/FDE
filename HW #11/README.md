# Day 8 · Student files

Copy these folders into the root of your course repository, `ai-engineer-course/`, keeping the folder names: `app/`, `scripts/`, `tests/`, `data/`, `logs/`. Nothing in them overwrites a file you edited on Days 6 or 7. Then copy the new setting `JUDGE_MODEL` from `.env.example` into your own `.env`.

Today needs your working Day 6 and Day 7 code (all TODOs completed), the policy index (29 chunks), and Ollama running.

Every exercise runs through Claude Code: you ask, it proposes the command, you approve it.

## Lecture deck

| File | Slide | What it is for |
|---|---|---|
| `.env.example` | 5 | The new setting for today: the judge model |
| `data/Day08_Slide25_chatbot_answers.csv` | 25, 32 | 12 saved chatbot answers, with their sources and a person's labels (correct? grounded?) |
| `app/answer_checks.py` | 25 | The behaviour check (done). Activity 1: fill in `check_citations()` |
| `tests/test_answer_checks.py` | 25 | Tells you when Activity 1 is done: five tests |
| `scripts/eval_answers.py` | 25, 32 | Checks every answer (code checks, and the judge unless `--no-judge`); `--live` asks the chatbot first |
| `app/judge.py` | 32 | The judge prompt and reading its verdict (done). Activity 2: fill in `judge_answer()` |
| `tests/test_judge.py` | 32 | Tells you when Activity 2 is done: five tests |
| `app/quality_gate.py` | 38 | Activity 3: fill in `quality_gate()` |
| `tests/test_quality_gate.py` | 38 | Tells you when Activity 3 is done: five tests |
| `data/Day08_Slide37_quality_thresholds.json` | 37, 38 | The agreed thresholds the gate checks against |
| `scripts/quality_gate.py` | 38, 44 | Runs the evaluations, prints PASS or FAIL (exit code 0 or 1) and saves `data/quality_report.json` |
| `app/scorecard.py` | 44 | The eight-dimension scorecard (provided, nothing to fill in): eight probe questions and the PASS / FAIL / UNTESTED rules |
| `scripts/scorecard.py` | 44 | Asks the probes, reads `data/quality_report.json`, prints all eight dimensions with evidence and saves `data/scorecard.json` |
| `tests/test_scorecard.py` | 44 | Five tests with a fake chatbot that show how each verdict is decided |
| `tests/day08_fakes.py` | 25–38 | A fake model the tests use, so no unit test calls a real model |
| `logs/Day08_Activity_Log.md` | All activities | Record your results, including your verdicts on the scorecard; submit it with your homework |

Activity 4 (slide 44) runs `scripts/quality_gate.py` once more in your default mode, then `scripts/scorecard.py`.

## Homework deck

| File | Slide | What it is for |
|---|---|---|
| `data/Day08_HW_Slide05_quality_thresholds_template.json` | 5 | A starting point for your own thresholds |

## Stretch exercise

`Day08_Exercise_RAG_Chatbot_Evaluation.docx` (shared separately) adds all eight evaluation dimensions to your Days 6–7 IT Help Desk chatbot project. It takes about 4 hours; do it over the next week.

## Before Day 9

Day 9 tests the chat app in a browser with Playwright. Ask Claude Code to install it before class: `pip install pytest-playwright`, then `playwright install chromium` (about 150 MB).

All data is invented: no real company, people or policies. The code files keep plain names because Python imports them by name.
