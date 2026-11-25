# ADR-008: A small model for the remediation's documents

**Status:** <proposed or accepted>  ·  **Date:** <date>  ·  **Deciders:** <who>

## Context

<!-- What Martin asked for: the proof-of-address remediation (1.2 million customers over 12 months, about 100,000
     documents a month on top of 8,600), and an answer at the branch counter within 2 seconds. Helen's rule: the cascade
     lets through no more errors than the pilot (ADR-003). The UK rule from ADR-002 for any model call. -->

## Options considered

### Option A: the pilot reads every document (ADR-003, as today)

<!-- Errors that slip through, fields to a person, Sonnet calls, the time to an answer: from Model lab → Cascade. -->

### Option B: a small model the bank runs, taught by the pilot, with the pilot for the rest (the cascade)

<!-- Trained on which reads, and why only those (ENG-1101). How sure a field is (ENG-1102). Which documents go to the
     pilot, and the threshold you chose from the curve (ENG-1103). -->

### Option C: fine-tune a small open-weight language model and host it at the bank

<!-- What it would need (GPUs, a day of training, a model team) and what it might add (documents the tagger cannot
     read). Argued, not measured: say so. -->

| | Option A | Option B | Option C |
|---|---|---|---|
| Errors that slip through (October) | | | |
| Fields to a person | | | |
| Answered at the counter | | | |
| A month today (8,600 documents) | | | |
| A month in the remediation (108,600) | | | |
| What the bank must run | | | |

## Decision

<!-- Which option, at which threshold, and why. -->

## What it costs to own

<!-- The host, the monthly retrain and its check, the volume from which it pays (Model lab → Client scale). Which
     numbers are measured and which are Martin's estimates. -->

## When we retrain, and how we know

<!-- The spot checks, a new kind of document, a change to the pilot's model or prompt. -->

## Consequences

<!-- What gets better, what gets worse, what we watch. -->
