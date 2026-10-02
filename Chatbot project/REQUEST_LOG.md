# Request Log

Every request sent to Claude Code, with one line on what happened.

## Phase 0: Documents, test questions, requirements
1. Gave Claude the Day 6 brief PDF and asked it to understand it and plan the project, pushing to the FDE repo. Result: plan written; choices made: push into a new `Chatbot project` folder, and Claude drafts the documents for me to review.
2. Approved the plan: build everything from scratch, copy nothing from other course folders. Result: Claude drafted 17 fictional Northwind IT documents, `data/test_questions.csv` (7 answerable, 3 not) and REQUIREMENTS.md.
3. "Happy with phase 0, continue to phase 1." Result: documents and questions accepted as drafted.

## Phase 1: Project skeleton and rules
4. Create the project skeleton: venv, git, .gitignore (.env and vector DB), requirements, CLAUDE.md with commands, structure and rules; documents and questions in `data/`. Result: created, see commit.
5. Asked Claude to summarise the CLAUDE.md rules back in its own words. Result: all 10 rules restated correctly, so CLAUDE.md is clear.

## Phase 2: Loader and chunker
6. Build a loader for .pdf/.txt/.md (page by page, keeping page numbers), a chunker (size 500, overlap 100), tests for size, overlap, short, empty and invalid settings, and a chunk report script that flags documents with no chunks; warn and skip unreadable documents. Result: 16 tests pass; 17 documents gave 33 chunks, none empty. Noted: chunks can cut mid-sentence (a known limit of fixed-size chunking). Corrected the document count from 16 to 17.

## Phase 3: Embeddings and vector store
7. "Go" with collection `it_helpdesk` and rebuild-from-scratch; also asked Claude to open the relevant files for each phase in the main editor. Result: Ollama embeddings (with nomic task prefixes), persistent Chroma collection with source/page/chunk metadata, `scripts/build_index` (and `--count`), 5 new tests (21 total, offline). Build gave 33 chunks; a fresh process counted 33 from disk without embedding; `data/chroma` not tracked by Git.

## Phase 4: Retrieval
8. "Go for 4" chunks. Build `search(question, k)` returning text, source, page, chunk and similarity score, plus a retrieval-only `scripts/search`. Result: 27 tests pass offline. Right document at or near the top for 4 answerable questions (scores 0.61-0.81). Salary question scored 0.51 (clearly lower), but near-miss questions (printer floor 3: 0.72, Linux laptops: 0.71) score as high as real answers, so a minimum score alone cannot catch them: Guard 2 in Phase 5 must.

## Phase 5: Grounded answers and guards
9. "Go" with my decline sentence (service desk ext. 4357 / servicedesk@northwind.example), minimum score 0.55, temperature 0.1. Build the grounded prompt, Guard 1 (score, no model call), Guard 2 (decline sentence), a result with answer/sources/declined, and tests with fake model and retriever. Result: 38 tests pass offline. Also decided: an answer with no valid [n] citation is treated as declined, and `</source` inside a document is escaped. Live check: backups question answered with a correct citation (runbook page 1); salary question declined by Guard 1 with no sources; floor 3 printer near-miss declined by Guard 2.

## Phase 6: Chat interface
10. "Go" with the three error messages (index missing, model unreachable, empty question). Build the Streamlit app with Chat, Knowledge base and Test results tabs, sidebar status/settings/last-question details, DECLINED badge, rebuild button and retrieval-only search; start it in the background. Result: 45 tests pass (including headless app smoke tests). First launch silently failed because an old class app held port 8501 and I wrongly reported it as mine; I stopped the old app (with permission) and ran mine on 8502. Screens checked in the browser: cited answer with source tag, DECLINED badge with no sources, knowledge base table, 3 tabs. Test results tab and "latest test run" are placeholders until Phase 7. App stopped before commit.

## Phase 7: Test, tune and show results
11. "Go" with a 3-second pause between questions. Build the test runner (saves run_N.json/csv with question, expected, behaviour, answer, sources, time), the summary, the Test results tab and the sidebar latest-run/run-history panel. Result: 53 tests pass offline. Run 1 (min score 0.55): 10/10, 7/7 answered, 3/3 declined, avg 3.86 s; I read every answer and citation against the documents and all were correct.
12. Chose to tune the minimum score 0.55 -> 0.65. Result: run 2 scored 9/10 (question 7 "lost phone", score 0.61, wrongly declined by Guard 1). Decision: keep 0.55. Both runs and the reasoning are in data/results/TUNING.md.

## Phase 8: Security review (part 1 of 2: review and fixes)
13. "Can the Day 2 security-reviewer be reused, or built from scratch?" Brief says "using your Day 2 security-reviewer subagent if you have it". Searched the machine: none exists. Also asked whether Day 5 lessons may be used (yes: lessons, not copied code). Result: wrote a new read-only `security-reviewer` subagent inside the project (`.claude/agents/security-reviewer.md`).
14. "Go": ran the whole-project review. The new agent file is only loaded at startup, so the review ran as a general-purpose agent told to follow that file. Result: 17 findings (0 High, 5 Medium, 10 Low, 2 Info). I checked separately that `.env` was never committed.
15. Chose which findings to fix now: network and errors, prompt and rendering safety, limits and input checks, safe rebuild, test safety net, dependencies and files. Left as known limits: per-sentence citation check, file size limit/caching, symlinks. Result: all chosen fixes made with tests (93 tests pass offline); real checks done: rebuild with the swap logic gave 33 chunks, live answers and declines still correct, app on 127.0.0.1 refuses LAN connections. Full table in SECURITY_REVIEW.md.

## Phase 8: README and hand-in (part 2 of 2)
16. "Go" for the README. Before writing it I noticed no test had ever read a real PDF (all 17 documents are markdown), so I added tests that build small PDFs: page numbers kept, a text-less "scanned" PDF gives no chunks, a corrupt PDF is reported not fatal. Then wrote README.md (what it does, set-up, run, rebuild, tests, results, settings, known limits). 96 tests pass offline.
17. Provided four screenshots (chat with a cited answer and a DECLINED badge, knowledge base, test results for run 1 and run 2) and wrote the reflection in my own words; Claude fixed spelling and grammar only. Result: saved in `screenshots/` and `REFLECTION.md`.
18. "Go": stop the app, final commit and tag `v1.0-day6`. Result: see git log. Push to the FDE repo waits for approval.

## After hand-in: look-and-feel polish
19. Asked for recommendations to make the app look better; chose items 1-5 and 7. Result: friendlier knowledge base name ("Northwind IT docs"), proper table headers, three clickable example questions, a welcome message, a Clear chat button, and a green OK / red MISS colour on the Test results table with red "missed" markers on the cards. 100 tests pass offline (4 new). Checked on screen: Run 2 shows the miss clearly.
20. Said "no need" to committing, then changed my mind: "push them". Result: committed as v1.1-day6 and pushed to the FDE repo.
