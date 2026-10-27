# REQUEST_LOG.md

Every request sent to Claude Code on this project, with one line on what happened. (Claude Code wrote the code; the person made the decisions and checked the results.)

| # | Date | Request (short) | What happened |
|---|---|---|---|
| 1 | 2026-10-26 | Read the capstone brief, the Day 1 guide and the starter kit | Read both PDFs and the kit; summarised the plan, the 13 prompts and what was needed before starting |
| 2 | 2026-10-26 | Do Day 1 completely, no missing anything | Built Prompts 1-13 (setup, models, sign-in, console, voice note, transcription, rubric, wording check, approval, apply page, CV reading, review queue and identity hiding, supervisor and pipeline) plus both stretch items; 116 tests; extraction 96/96 |
| 3 | 2026-10-26 | Follow the instructor's naming exactly, and open files in the main editor | Used `hiring-intelligence` and `starter_kit` and the guide's file names; opened files with `code -r` |
| 4 | 2026-10-26 | Stop and run the app | Started it on port 8001 (8000 was taken) with the demo data |
| 5 | 2026-10-26 | Give me the demo accounts; explain what Prompts 4 and 5 should show | Listed the two accounts and what each page should show |
| 6 | 2026-10-26 | Push to GitHub | Pushed Day 1 to `FDE/Capstone` with its history |
| 7 | 2026-10-26 | Show me the real database and explain it | Showed the SQLite tables read-only; recommended the SQLite Viewer extension; explained each table |
| 8 | 2026-10-26 | Here is the full capstone brief; finish the entire thing; how long will it take? | Estimated 6-10 hours; listed what was missing (the Days 2-4 starter kit) and asked 3 questions |
| 9 | 2026-10-26 | Make the missing data yourself; stay in fake mode but make real models easy; start tomorrow 11:30 | Agreed; saved the decisions |
| 10 | 2026-10-26 | Make a detailed plan first | Wrote the plan: Stage 0 (fictional kit), Days 2-4, reports, switching to real models |
| 11 | 2026-10-26 | Only at the very end, restyle everything to look like a sellable product | Recorded as Stage 5, to be done once, after everything else is green |
| 12 | 2026-10-27 | Go ahead and do the entire thing, full auto, no approvals | Built Stage 0 (fictional starter kit), Day 2 (scoring, shortlist, interviewer, assistant, MCP), Day 3 (copilot, communications, compliance, guardrails, supervisor graph, ops, Docker, red team) and Day 4 (scorecard, decisions, bias, cost and speed, governance, journey), the reports and the Playwright tests |

Sub-requests inside request 12 (what Claude Code was asked to do, in order): fictional question bank and diagrams; policy, calendar, 20-attack library; extra CVs, bias variants and ranking keys; recorded
answers, interviews and accent set with a speech engine; model router, cost ledger and tracing; agent framework with least-privilege tools; screening with quote verification; shortlist and approval gate; AI interviewer
with state saved every turn; interview pages; recruiter assistant with streaming; tracking database and MCP server; communications and outbox; interview copilot; compliance reviewer; guardrails; supervisor as a LangGraph
graph; /ready and /metrics; Dockerfile, compose and CI; red team before and after; ranking, interview and copilot evaluations; quality gate; scorecard and decisions; explanation on request; Trust & cost tab; bias tests
(counterfactual and transcription with real Whisper); cost and speed measurements; governance pack and its check; retention purge; full journey script; Playwright tests; documentation.

Things that went wrong and were fixed (kept here because they were useful to learn from): SQLite silently dropped log writes made from a second connection (the prompt log and traces now live in their own database);
a failing first ranking evaluation (3/5) turned out to be ties in the key plus an over-generous scoring rule, fixed by reading the rubric wording, not by copying the key; the real-Whisper run needed PyAV pinned below
version 17; the red team's first run found a protected disclosure ("a member of a union") that the masking missed, fixed and re-run.
