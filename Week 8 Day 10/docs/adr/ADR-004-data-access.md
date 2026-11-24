# ADR-004: How the bank's people get answers from CaseFlow

**Status:** proposed · **Date:** 2026-11-17 · **Deciders:** Deborah Okafor, Helen Achebe, Mithran Sadasivam

## Context

Today every number comes from the MI team's monthly pack. Deborah wants turnaround and backlog on demand, Grace wants her region's figures, Tom wants his team's, and Helen wants every team's cases without customer names. The bank's rules: read-only (nothing a question does may change CaseFlow), each person sees only their remit, and no customer names in Helen's MI.

## Options considered

### Option A: the model writes SQL over the raw extract

Free SQL over every table, the model told only the column names. The closest thing we measured is caseflow_v1, which has the tables and columns but none of the bank's words (it is still checked and secured, so it is safer than a true Option A).

### Option B: the model writes SQL from a semantic layer, checked and secured

caseflow_v2 (the tables, columns and the bank's words turnaround and backlog) + the validator (ENG-701) + row security (ENG-702) + a read-only warehouse.

### Option C: fixed metrics only

A list of approved metrics, each a query written by the MI team; the model only picks one and fills in the dates.

| | Option A | Option B | Option C |
|---|---|---|---|
| Right on the 30 questions | 20 of 30 (measured, caseflow_v1) | 28 of 30 (measured, caseflow_v2) | Not built. Estimate: right on questions that match a metric, no answer to those that do not |
| Can a query change or leak data? | Only if the checks are missing; measured with them: 15 of 15 harmful refused, 30 of 30 row checks | No: 15 of 15 harmful refused, 30 of 30 row checks, no leaks (measured) | No: the model writes no SQL (by design, not measured) |
| New questions without the MI team | Yes, but 10 of 30 wrong | Yes; a new word needs a definition first (the 20 harder questions: 6 of 20 right with v2) | No: each new question is a new metric from the MI team |
| Run cost a month | £8.75 (measured, v1) | £10.02 (measured, v2) | About £2 (estimate: a short prompt and no SQL, not measured) |

Costs are Claude Sonnet 5 in London on the scripted model's token counts, for 2,000 questions a month (an assumption). The two measured costs are from the Evaluation tab; Option C's is an estimate.

## Decision

Option B.

<!-- Mithran: the reasons for the decision go here, in your own words. -->

## Consequences

- **The bank must own** the semantic layer and its definitions (Deborah's MI team), and `access.yml`, the approved tables and each person's rows (Helen). The FDE does not own them after handover.
- **We will measure every month:** the 30 questions against Deborah's bar of 27, the 15 harmful queries refused, the 30 row-security checks with no leaks, and the cost a month against about £10.
- **When a question is refused or cannot be answered:** the person is told why in plain words, and nothing runs. Unanswered questions go to the MI team as candidates for a new definition, added as a new version of the layer, never an edit to an old one.
