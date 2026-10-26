# EVAL_REPORT: the 10 scenarios

Run: 2026-10-25 18:23 · model mode: **real** · large `anthropic/claude-haiku-4.5` · small `google/gemini-2.5-flash-lite`
· whole starter set triaged and briefed in **59.5 s**.

## Scorecard

| Check | Result | Decided by |
|---|---|---|
| grouping | 10/10 | rules |
| root cause | 10/10 | rules |
| severity | 10/10 | rules |
| status | 10/10 | rules, then the model's check |
| runbook step | 10/10 | model recommends, code checks |
| approvals | 10/10 | rules |
| similar | 10/10 | rules |
| flags | 10/10 | rules + guardrails |

Incidents produced: **10** (expected 10 from 22 alerts).

Model calls: 34 · tokens: 36,807 · cost: $0.0182 · cost per incident brief: $0.0023

## Scenario by scenario

| Scenario | Incident | grouping | root cause | severity | status | runbook step | approvals | similar | flags |
|---|---|---|---|---|---|---|---|---|---|
| S01 | INC-3001 | yes | yes | yes | yes | yes | yes | yes | yes |
| S02 | INC-3002 | yes | yes | yes | yes | yes | yes | yes | yes |
| S03 | INC-3003 | yes | yes | yes | yes | yes | yes | yes | yes |
| S04 | INC-3004 | yes | yes | yes | yes | yes | yes | yes | yes |
| S05 | INC-3005 | yes | yes | yes | yes | yes | yes | yes | yes |
| S06 | INC-3006 | yes | yes | yes | yes | yes | yes | yes | yes |
| S07 | INC-3007 | yes | yes | yes | yes | yes | yes | yes | yes |
| S08 | INC-3008 | yes | yes | yes | yes | yes | yes | yes | yes |
| S09 | INC-3009 | yes | yes | yes | yes | yes | yes | yes | yes |
| S10 | INC-3010 | yes | yes | yes | yes | yes | yes | yes | yes |

## How the models behaved

- Planner attempts: **8** for 8 actionable incidents; Verifier rejections: **0** (each is retried once, then the incident stops for a person).
- Investigator: **15** [READ] tool calls; **4** time(s) the model's reply could not be used and the tower ran the runbook's [READ] steps in order instead.
- The planner model sees alert text only after hiding and the input check; flagged alert text is withheld entirely.

## Misses

None: every check passed on every scenario.

## How to read this

- *grouping, root cause, severity, approvals, similar incident* are plain Python (`tower/triage.py`) and score the same with or without a model.
- *runbook step* and *status* depend on the model: a recommendation that fails the code check is retried once, then the incident stops as NEEDS_PERSON.
- `scripts/run_scenarios.py --model real --report` regenerates this file.
