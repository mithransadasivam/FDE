# Day 18 weekend project: starter data

Everything here is fictional, made up for a training exercise: the company, its policy, the services, the
people, the alerts and the past incidents. Email addresses and host names use example.com, phone numbers use
the UK range kept for drama (+44 7700 900xxx), and the IP address 203.0.113.45 is from a range kept for
documentation. The "secrets" in alert AL-119 are made up too.

## What is in the pack

| File | What it is |
|---|---|
| docs/OPERATIONS_POLICY.md | The rules for severity, grouping, runbooks, approvals and data, in numbered sections your system should cite (for example 5.3) |
| docs/runbooks/RB-01.md … RB-08.md | Eight runbooks. Each step is [READ] (may run without approval) or [CHANGE] (needs approval) |
| data/services.csv | The service catalogue: 12 services with tier, owning team, dependencies and runbooks |
| data/oncall.csv | The on-call engineer for each team, and the duty manager. PRIVATE: personal_mobile must never reach a model, a log or the screen (policy 7.3) |
| data/alerts.csv | 22 alerts from Thursday 22 to Saturday 24 October 2026, from three monitoring sources |
| data/incidents_history.csv | 16 past incidents and what fixed them |
| data/scenarios.csv | The expected result for 10 scenarios: which alerts, root cause, severity, status, runbook step, action, approvals, similar past incident and flags |
| data/operator_questions.csv | 30 questions operators ask, with a weight (how often each is asked), for your load test |
| data/attacks.json | Six starter attacks, each with the place it comes in and a rule for when it worked |
| governance/model_card_template.json | The fields a model card for the tower must have, all empty, for Part 4 |
| governance/risk_register_template.json | The fields of one risk, with one worked example (R01) for Part 4 |

## Statuses used in scenarios.csv

- WAITING_FOR_APPROVAL: the incident has a recommended [CHANGE] step and is waiting for the approvals listed
- AUTO_RESOLVED: every alert cleared by itself (policy 2.5 and 3.4); nothing to do
- NEEDS_PERSON: the system must not guess (policy 3.3)

approvals_needed counts people: 1 is the owning team's on-call, 2 adds the duty manager (policy 5.2, 5.3).

## The traps, on purpose

Two alerts for one disk (S01); a recent deploy that tempts a rollback when the cache is the cause (S02);
five alerts from four services with one root cause (S03); a latency alert that keeps clearing by itself (S04);
a warning that needs action this week but not tonight (S05); an alert that tells the AI to restart
everything (S06); a change during the freeze that is not P1 but still needs two approvals (S07); a
password, a token and a personal mobile inside an alert (S08); two monitoring sources reporting one problem
(S09); and a service that is not in the catalogue (S10).
