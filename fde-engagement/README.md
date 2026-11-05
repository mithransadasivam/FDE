# fde-engagement · Day 1 student files

This is the start of a **new repository** for Phase 2. You build the same product, the FDE Engagement Console, for the fictional client Kestrelmoor Bank across all 15 days.

## Set up (Activity 1)

Copy the folder `fde-engagement/` to where you keep your projects, open it in VS Code and start Claude Code in it. Then send the Activity 1 prompt from the slides. Claude Code will:

1. create a virtual environment and run `pip install -r backend/requirements.txt`
2. run `npm install` and `npx playwright install chromium` in `frontend/`
3. copy `.env.example` to `.env` (you paste in your OpenRouter key yourself)
4. run the tests that pass from the start: `python -m pytest -q tests/test_smoke.py` (5 tests) and `npx playwright test e2e/smoke.spec.ts` (2 tests)

Start the console with `cd frontend && npm run dev` and open http://localhost:5173.

## Files

| File | Slide | What it is for |
|---|---|---|
| `data/Day01_Slide06_phase2_setup_checklist.md` | 6 | What to install today, and the accounts to create before Days 5 and 8 |
| `data/Day01_Slide10_client_brief.md` | 10 | The client brief. The console's **Brief** tab shows it |
| `backend/app/discovery/questions.py` | 10 | Drafts the question plan from the brief (done) |
| `data/Day01_Slide21_discovery_transcript.md` | 16, 21 | The reference recording of the full discovery session. Read it after the role-play |
| `backend/app/discovery/findings.py` | 21 | **Ticket ENG-101:** fill in `extract_findings()` and `verify_evidence()` |
| `docs/tickets/ENG-101.md` | 21 | The ticket: story, acceptance criteria, tests |
| `backend/tests/test_findings.py` · `frontend/e2e/findings.spec.ts` | 21 | Tell you when ENG-101 is done: 9 + 4 tests |
| `data/Day01_Slide26_success_criteria_draft.json` | 26 | Three draft success criteria, one of them vague |
| `data/Day01_Slide26_use_case_candidates.csv` | 26 | Five candidate use cases with value, feasibility and risk |
| `backend/app/discovery/criteria.py` | 26 | **Ticket ENG-102, part A:** fill in `check_criterion()` |
| `frontend/src/components/UseCaseMatrix.tsx` | 26 | **Ticket ENG-102, part B:** build the matrix |
| `docs/tickets/ENG-102.md` | 26 | The ticket |
| `backend/tests/test_criteria.py` · `frontend/e2e/success.spec.ts` | 26 | Tell you when ENG-102 is done: 7 + 4 tests |
| `CLAUDE.md` | All | The rules Claude Code follows in this repository |
| `engagement/` | All | Your team's work, saved by the console as JSON and Markdown. Commit it |

## Homework files

| File | Slide | What it is for |
|---|---|---|
| `data/Day01_HW_Slide03_review_history.csv` | 3 | A random sample of 5,002 completed document reviews from the last four weeks, with minutes spent and outcome |
| `data/Day01_HW_Slide03_backlog_export.csv` | 3 | The 4,200 documents waiting today |
| `data/Day01_HW_Slide03_data_check_template.md` | 3 | Where you record what the data says |
| `data/Day01_HW_Slide04_constraints_template.md` | 4 | The regulation and constraints map |
| `data/Day01_HW_Slide05_followup_email_template.md` | 5 | The follow-up email to Deborah |

## Good to know

- **Scripted model mode.** The end-to-end tests set `FDE_FAKE_LLM=1`, so they use the replies in `backend/tests/fixtures/` instead of a real model. They also run on their own ports (8010 and 5183) and in their own folder (`.e2e/`), so they never touch your work.
- **Your key.** It goes only in `.env`, which git ignores.
- **Fictional data.** Everything is invented: the bank, its people, systems, documents and numbers.
