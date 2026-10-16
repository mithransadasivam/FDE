# Vendor Onboarding Desk

A fictional procurement team (Marlowe & Finch Ltd) gets supplier onboarding requests by email. **Agents do the checking; a person
makes every decision.** Requests in, agents check (documents, duplicates, watch list, bank, terms, spend), a person approves,
every step is on record. Built for the Days 12-14 homework: a planning agent, a procurement MCP server, and a supervisor-led team
with an approval gate.

```
email / web form -> intake -> documents + finance -> compliance -> reviewer (code) -> follow-up draft
                       (supervisor rule, LangGraph, checkpoints in SQLite)
                                   -> STOPPED | WAITING_FOR_VENDOR | READY_FOR_APPROVAL
                                   -> a person approves (two different people above £25,000) -> create_vendor (the only write)
```

Everything is fictional: companies, people, bank details (account numbers start 99), `example.com` addresses.

## Run it (Python 3.11+; Node 22.19+ only for MCP Inspector)

```bash
python -m venv .venv
.venv/Scripts/activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

python -m scripts.build_db        # builds data/procurement.db from data/seed/*.csv and prints the counts (run again to reset)
python -m pytest -q               # all tests: no network, no real model, a temporary database
python -m scripts.seed_demo       # (optional) runs every request offline and acts as a few approvers: a busy inbox
streamlit run app.py              # Mission Control: board, case file, flight recorder, arena, what-if lab, red-team lab, intake portal
```

No API key is needed: the **offline demo model** (`vendor_desk/offline_llm.py`) is a rule-based stand-in that speaks the same
chat/tool-call protocol as a real model. For the hosted model, copy `.env.example` to `.env`, set `OPENROUTER_API_KEY` and
`LLM_MODEL`, and pick "Live model" in the app's sidebar (or pass `--llm live` to a script).

### Start the MCP server

```bash
python -m vendor_desk.mcp_server                    # stdio, read-only; create_vendor is not even listed
VENDOR_WRITES=on python -m vendor_desk.mcp_server   # offers create_vendor (the approval gate does this for one call only)
python -m scripts.inspector_tour                    # tours every tool/resource/prompt in MCP Inspector (needs Node + internet)
claude mcp add --scope project procurement -- python -m vendor_desk.mcp_server   # register it for Claude Code (see .mcp.json)
```

In Claude Code you can then ask "which vendors use 60-day terms?", and run the prompt with
`/mcp__procurement__assess_request VOB-007`. Set `TOOLS_BACKEND=mcp` (or choose "MCP server" in the app) to make the agents get
their tools from the server.

### Scripts

| Command | What it does |
|---|---|
| `python -m scripts.run_case REQ-007 --llm offline` | One request through the single planning agent: trace, assessment, draft follow-up, trace review |
| `python -m scripts.run_case REQ-001-R1 --llm offline` | A vendor reply: continues the case from its notes |
| `python -m scripts.run_all --llm offline` | All 19 cases through the single agent; writes the Part 1 section of `EVAL_REPORT.md` |
| `python -m scripts.run_team_case REQ-004 --llm offline --fault compliance=wrong` | One request through the team, printing each handoff; the reviewer sends a deliberate error back |
| `python -m scripts.run_team_case REQ-009 --llm offline --approve a@example.com --approve b@example.com` | Two approvers, then the one write |
| `python -m scripts.compare --llm offline` | Single agent vs team on all cases: decisions, calls, tokens, seconds; writes the Part 3 section |
| `python -m scripts.ask_claude_code` | Asks Claude Code questions through the MCP server (`docs/CLAUDE_CODE_ANSWERS.md`) |

`--llm live` needs the key; the account allows about 20 calls a minute, so live runs wait between calls. `ENV_FILE=/path/to/.env`
loads a `.env` kept outside the project.

## What is where

| Path | What |
|---|---|
| `docs/ONBOARDING_POLICY.md` | The numbered policy every agent cites (§3.2 and so on) |
| `data/requests/`, `data/onboarding_cases.csv` | 18 request emails + 1 vendor reply, their documents, and the expected result for each |
| `vendor_desk/tools.py` | The read-only checks with JSON Schemas |
| `vendor_desk/agent.py` | Part 1: the planning agent (step limit, repeat stop, trace) |
| `vendor_desk/mcp_server.py`, `mcp_client.py` | Part 2: the MCP server and the agent's client |
| `vendor_desk/team.py`, `specialists.py`, `states.py`, `casedesk.py` | Part 3: supervisor, specialists, states, approval gate |
| `vendor_desk/audit.py` | The hash-chained audit trail (`runs/team/<case>/audit.jsonl`) |
| `docs/DECISIONS.md`, `docs/SECURITY_REVIEW.md`, `REFLECTION.md` | The decisions, the security review, the reflection |
| `EVAL_REPORT.md`, `REQUEST_LOG.md` | Results (Part 1 and Part 3) and the log of every request sent to Claude Code |

## Beyond the brief

A tamper-evident audit trail (hash chain, verified in the app); shared-bank-account and account-holder fraud checks; case notes
with the source of every finding; escalation of stale cases (policy §9: manager's queue, then expiry); a web-form second channel
that makes the same case as an email; parallel checks; a model-as-supervisor option guarded by the code rule
(`SUPERVISOR=model`); a spy-model test that no private data ever reaches a prompt; HTML-escaped display of untrusted text; and a
separate evaluation database so the demo never skews the numbers.

## Notes for the colleague running this

- Approving in the app really creates a vendor row in `data/procurement.db`; **Reset demo data** (sidebar) rebuilds it.
- The live-model numbers in `EVAL_REPORT.md` were limited by the API key's spending cap; the offline baseline numbers are
  complete and reproducible.
