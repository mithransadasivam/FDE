# Day 18 · Student files

Copy everything in this folder into the root of your course repository, `ai-engineer-course/`, keeping the folder names. Commit your Day 17 work first. Nothing here replaces a file you wrote: today's files are all new. Nothing to install.

Then, through Claude Code (slide 5): run `pytest -q tests/test_governance_parts_day18.py` (7 tests pass) and look at `governance/`.

**governance/** holds the governance documents as data, next to the code: `model_card.json` (a starter with gaps, on purpose) and `risk_register.json` (four of the eight risks). Today's scripts turn them into pages for people: `use_case_inventory.md`, `MODEL_CARD.md` and `GOVERNANCE_PACK.md`. `scripts/collect_evidence.py` copies the reports from earlier labs into `governance/evidence/` with a fingerprint and a manifest. Commit the whole `governance/` folder: unlike `logs/`, it is part of the record.

Evidence it looks for: Day 8's `data/quality_report.json` (`python -m scripts.quality_gate`), Day 16's `logs/load_after.json`, Day 17's `logs/red_team_before.json` and `logs/red_team_after.json`, and today's `logs/bias_report.json`. A missing one is listed with the command that makes it. `CHAT_FAKE=1` makes the bias test, the red team and the load test fast and free.

Today's classifications and dates are for learning, not legal advice. The EU AI Act dates follow the Digital Omnibus on AI (2026).

## Lecture deck

| File | Slide | What it is for |
|---|---|---|
| `app/ai_act.py` | 8, 9 | The EU AI Act lists, obligations and dates (done). Activity 1: fill in `classify_use_case()` |
| `tests/test_ai_act.py` | 9 | Tells you when Activity 1 is done: 7 tests |
| `data/Day18_Slide09_use_cases.json`, `scripts/classify_use_cases.py` | 9 | Four use cases, and the script that classifies them and writes `governance/use_case_inventory.md` |
| `app/fairness.py` | 13, 14 | Profiles, questions, the judge and the test runner (done). Activity 2: fill in `compare_answers()` |
| `tests/test_fairness.py` | 14 | Tells you when Activity 2 is done: 6 tests |
| `data/Day18_Slide14_user_profiles.json`, `data/Day18_Slide14_bias_questions.csv`, `scripts/bias_test.py` | 13, 14 | Five invented users, five questions (with a second-language version), and the script that writes `logs/bias_report.json` |
| `app/evidence.py`, `scripts/collect_evidence.py` | 19, 20 | Copies the evidence into `governance/evidence/` with fingerprints and a manifest (done) |
| `app/model_card.py`, `scripts/model_card.py` | 19, 20 | The required sections and the page (done). Activity 3: fill in `card_gaps()` |
| `tests/test_model_card.py` | 20 | Tells you when Activity 3 is done: 5 tests |
| `app/risk_register.py` | 23, 25 | Ratings, functions and statuses (done). Activity 4: fill in `check_register()`. Homework: `overdue()` |
| `tests/test_risk_register.py` | 25 | Tells you when Activity 4 is done: 6 tests |
| `data/Day18_Slide25_nist_rmf_assessment.md` | 23, 25 | The NIST AI RMF questions for each function, and the four findings to add to the register |
| `scripts/governance_pack.py` | 25 | Builds `governance/GOVERNANCE_PACK.md`; exit code 1 if the register or the card fails its checks |
| `governance/model_card.json`, `governance/risk_register.json` | 19, 23 | The starter model card and risk register |
| `tests/test_governance_parts_day18.py` | 5 | Tests for the finished parts (they pass from the start) |
| `logs/Day18_Activity_Log.md` | All activities | Record your results; submit it with your homework |

## Homework deck

| File | Slide | What it is for |
|---|---|---|
| `tests/test_overdue.py` | 3 | Tells you when Task 1 (`overdue()` in `app/risk_register.py`) is done: 4 tests |
| `scripts/check_register.py` | 3, 5 | Checks any register and lists overdue reviews |
| `data/Day18_HW_Slide04_my_use_case_template.json` | 4 | The questionnaire for your capstone: copy to `data/my_use_cases.json` |
| `data/Day18_HW_Slide05_capstone_risk_register_template.json` | 5 | One example risk: copy to `governance/capstone_risk_register.json` |

All data is invented: no real company, people, systems or documents. The code files keep plain names because Python imports them by name.
