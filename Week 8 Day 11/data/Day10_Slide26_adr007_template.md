# ADR-007: How a KYC case keeps going for days

**Status:** <proposed or accepted>  ·  **Date:** <date>  ·  **Deciders:** <who>

## Context

<!-- What Grace asked for: cases that wait days for an applicant and for a person's decision, a reminder on day 3 and an
     escalation on day 7, and no lost work when the console or the worker restarts. Helen's rules: who the work is done for,
     and that a message to an applicant is never sent twice. -->

## Options considered

### Option A: keep the Day 9 run, waiting in the console's memory

<!-- What a crash while Tom decides does, and what a crash on day 2 of the wait does. -->

### Option B: a durable workflow in the console (DBOS)

<!-- The checkpoints, the durable waits, the safe writes, the case grant. Tom's queue (Day10_Slide26_queue_expected.csv),
     with the worker crashing during it. -->

### Option C: a workflow server (Temporal)

<!-- The same model with its own cluster: what the bank would have to run, and what it adds. Argued, not measured: say so. -->

| | Option A | Option B | Option C |
|---|---|---|---|
| A crash while Tom decides | | | |
| A crash on day 2 of the wait | | | |
| A crash right after a write | | | |
| What the bank must run | | | |
| Run cost a month | | | |

## Decision

<!-- Which option, and why. -->

## How each write happens once

<!-- One line per write in data/Day10_Slide21_writes.csv: the key or the check, and the test that shows it. -->

## Who the workflow acts as

<!-- The case grant: what it allows, for how long, and when it is revoked. -->

## Consequences

<!-- What the bank runs (Postgres, workers), what happens when the workflow's code changes while cases are waiting, what we watch. -->
