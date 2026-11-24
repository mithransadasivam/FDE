# ADR-004: How the bank's people get answers from CaseFlow

**Status:** proposed · **Date:** <date> · **Deciders:** Deborah Okafor, Helen Achebe, <your name>

## Context

<!-- Today every number comes from the MI team's monthly pack. What Deborah, Grace, Tom and Helen want; the bank's rules: read-only, each person sees only their remit, no customer names in Helen's MI. -->

## Options considered

### Option A: the model writes SQL over the raw extract

<!-- Free SQL over every table, the model told only the column names. -->

### Option B: the model writes SQL from a semantic layer, checked and secured

<!-- caseflow_v2 + the validator (ENG-701) + row security (ENG-702) + a read-only warehouse. -->

### Option C: fixed metrics only

<!-- A list of approved metrics, each a query written by the MI team; the model only picks one and fills in the dates. -->

| | Option A | Option B | Option C |
|---|---|---|---|
| Right on the 30 questions | <n> | <n> | <n> |
| Can a query change or leak data? | <> | <> | <> |
| New questions without the MI team | <> | <> | <> |
| Run cost a month | <£> | <£> | <£> |

## Decision

<!-- Which option, and why, in two or three sentences. -->

## Consequences

<!-- What the bank must own (the semantic layer, the definitions, access.yml), what you will measure every month, and what happens when a question is refused. -->
