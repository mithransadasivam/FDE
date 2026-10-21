# Day 14 · Student files

Copy these folders into the root of your course repository, `ai-engineer-course/`, keeping the folder names: `app/`, `scripts/`, `tests/`, `data/`, `logs/`. Nothing in them overwrites a file you edited on earlier days.

Then install one new package, `pip install langgraph-checkpoint-sqlite` (add it to requirements.txt), and reset the database: `python -m scripts.make_helpdesk_db`.

Today needs your Day 12 code with its TODOs completed (the researcher is your Day 12 `run_agent()`), LangGraph from Day 12, the Day 6–7 index with Ollama running (for `search_policies`), and `OPENROUTER_API_KEY` in `.env`.

Every exercise runs through Claude Code: you ask, it proposes the command, you approve it. In Activity 3 you are the person who approves the notice: type your own decision and comment into the prompt.

## Lecture deck

| File | Slide | What it is for |
|---|---|---|
| `app/handoffs.py` | 8, 9 | The handoff models (ResearchNotes, Notice, Review) and `ask_for()`, which retries once (done). Activity 1: fill in `parse_handoff()` |
| `tests/test_handoffs.py` | 9 | Tells you when Activity 1 is done: 7 tests |
| `data/Day14_Slide09_notice_style_guide.md` | 9 | The style guide the writer follows and the reviewer checks |
| `data/Day14_Slide09_research_notes.json` | 9 | Five facts about the Finance Portal outage, for trying the writer on its own |
| `scripts/try_writer.py` | 9 | Runs only the writer on those facts and prints the checked Notice |
| `app/team.py` | 14, 20 | The team: prompts, specialists, the graph and publishing (done). Activity 2: fill in `route()`. Activity 3: fill in `human_approval()` |
| `tests/test_team_route.py` | 14 | Tells you when Activity 2 is done: 12 tests |
| `scripts/write_notice.py` | 14, 20 | Runs the team on one topic. It pauses for a person and saves its state in `data/team_checkpoints.db`; `--thread … --decision approve/revise/reject --comment "…"` carries on. Approved notices go to `outbox/notices/` |
| `tests/test_human_approval.py` | 20 | Tells you when Activity 3 is done: 5 tests |
| `app/meter.py` | 25 | Counts model calls and tokens per agent (done) |
| `app/notice_checks.py` | 25 | Activity 4: fill in `check_notice()` |
| `tests/test_check_notice.py` | 25 | Tells you when Activity 4 is done: 5 tests |
| `data/Day14_Slide25_notice_topics.csv` | 25 | Three topics, with the terms each notice must contain |
| `scripts/compare_team.py` | 25 | Runs the team (until its draft is ready for approval) and a single agent on the same topics, and compares calls, tokens, time and problems. Saves both notices in `logs/team_comparison.jsonl` |
| `tests/test_team_parts.py`, `tests/day14_fakes.py` | – | Tests for the finished parts (they pass from the start), and scripted model replies so no test calls a real model |
| `logs/Day14_Activity_Log.md` | All activities | Record your results; submit it with your homework |

## Homework deck

| File | Slide | What it is for |
|---|---|---|
| `data/Day14_HW_Slide04_notice_topics_template.csv` | 4 | The format for your five comparison topics |
| `data/Day14_HW_Slide05_fact_checker_results_template.md` | 5 | The results write-up and your decision |

`build_team()` has four extension points for the homework, so you never need to change `app/team.py`: `extra_nodes`, `route_fn`, `state_schema` and `feedback_fn`.

Keep `data/team_checkpoints.db`, `logs/team_comparison.jsonl` and `outbox/` out of git. Nothing is sent anywhere: "publishing" writes a Markdown file.

All data is invented: no real company, people, systems, tickets or vendor articles. The code files keep plain names because Python imports them by name.
