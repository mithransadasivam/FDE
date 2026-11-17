# ADR-003: <the extraction pipeline decision, in a few words>

- **Status:** proposed
- **Date:** Day 6 of the engagement
- **Deciders:** <who signs this off: Deborah for the Review queue, Helen for the rules, Martin for the cost>
- **Builds on:** ADR-001 (grounded extraction), ADR-002 (the pilot platform)

## Context

<What the October batch showed: what the bank sends (digital PDFs, scanned PDFs, JPGs), how well one keyer does today, and the volume. Three or four sentences, with numbers from Pipeline → Compare.>

## Options considered

| | Option A · <parser + LLM, confidence routing> | Option B · <parser + LLM, checked by a vision model> | Option C · <vision model only> |
|---|---|---|---|
| Fields right before review | | | |
| Fields sent to a person | | | |
| Errors that slip through | | | |
| Right after the review (one keyer today: …) | | | |
| Model cost a month (GBP, pilot model, 8,600 documents) | | | |
| Main risk | | | |

## Decision

<The option, and three reasons: errors that slip through (Deborah and Tom), every auto-accepted value printed on the page (Helen), cost (Martin).>

Also decided:
- **Vision prompt:** <which one, and why the first one failed>
- **Confidence threshold:** <the value, and what raising it would cost>
- **Running the month:** <calls at once, live or batch, and when the batch runs>

## Consequences

- **Good:** <…>
- **Bad:** <…>
- **To watch:** <the errors agreement cannot catch, and how you will find them>
