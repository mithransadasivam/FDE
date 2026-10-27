# TEAM_LOG.md

## Who did what

This capstone was built by **one person with Claude Code**, so the four roles in the brief were all played by the same person, with Claude Code writing the code.
The table shows which role's work each part is, so the split of the work is clear and could be handed to a team of four.

| Role (brief, section 14) | What it covers here |
|---|---|
| **A. Intake and screening** | `app/agents/requisition.py`, `document.py`, `screening.py`, `communications.py`, `compliance.py`, `app/search/`, `app/shortlist.py` |
| **B. Voice and interviews** | `app/ai/voice.py`, `app/agents/interviewer.py`, `copilot.py`, `app/interview/`, `app/voice/`, the question and diagram banks, `tests/test_browser.py`, the accent test |
| **C. Agents and platform** | `app/supervisor.py`, `app/supervisor_graph.py`, `app/agents/base.py`, the decision log, `mcp_server/`, `app/agents/assistant.py`, `ops/`, traces, `app/ai/router.py` |
| **D. Trust and quality** | `app/privacy.py`, `app/guardrails.py`, `app/evidence.py`, the evaluations, `scripts/run_red_team.py`, `run_bias_tests.py`, `build_governance.py`, the quality gate |

## Sessions

| Session | What was done | Checkpoint |
|---|---|---|
| 1 (Day 1) | Voice note to approved rubric; 52 CVs read in four formats; identity hidden; pipeline board; stretch: duplicates, second role | Extraction 96/96; blind records leak nothing; forbidden move refused; 116 tests |
| 2 (Day 2) | Scoring with verified quotes; shortlist and approval; AI interviewer; assistant; tracking MCP server | Every score has a verified quote; interview scoring 30/30 on the recorded answers; ranking overlap 5/5, 4/5, 4/5 |
| 3 (Day 3) | Copilot; communications and outbox; compliance reviewer; guardrails; supervisor graph; ops endpoints; Docker; red team | Forbidden question flagged in milliseconds; planted fake quote caught; 20/20 attacks stopped after (5/20 before) |
| 4 (Day 4) | Scorecard and decisions; bias tests; cost and speed; governance pack; the whole journey; reports; Playwright | Governance check passes; journey has 0 decisions without a person; quality gate passes |

## Decisions the team made (the hardest ones)

- **Fairness: identity hiding comes from exact-match on the candidate's own details plus rules for age and gender proxies, not from a name detector.** Presidio's person detector wrongly hid tool names such as Grafana and
  Docker (which would have lowered scores for no reason), so it is used only for e-mails, phones and links.
- **Safety: a score without a verified quote becomes 0, even if the model is confident.** It makes the system slightly harsher on a model that paraphrases, and it makes injected "score 3" instructions useless.
- **Honesty: every report says it used fake models and says what was simulated** (the accent variants, model latency, prices).
- **Control: the "ask for a person" path is the only way to skip the AI interview, and the supervisor checks it in code** instead of trusting a button.

## Open items and tomorrow's first task

1. Run `python -m scripts.check_real_models` with a key, then `python -m scripts.quality_gate` with `FAKE_MODELS=0`, and compare with the fake-mode numbers.
2. Re-run the accent test with real accented speech (the Windows voices only give two voices).
3. Add an LLM judge as a second injection detector (accepted risk in `SECURITY_FINDINGS.md`).
4. Stage 5: restyle the console, the candidate pages and the interview page so the product looks sellable.
