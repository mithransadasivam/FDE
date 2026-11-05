# ADR-001: Read proof-of-address documents with OCR first, then a small model

- **Status:** proposed
- **Date:** 2026-11-03
- **Deciders:** Martin Hale (COO, sponsor), Deborah Okafor (Head of KYC Ops), Helen Achebe (MLRO, signs off KYC controls), Tom Reyes (senior analyst, user)

## Context

About 4,200 documents wait for an analyst, and a clean personal document takes about 6 minutes. UC1 reads a proof of address, shows four fields with a confidence, and boxes the doubtful ones. Any option must meet the client's rules: customer data stays in the UK (AWS London), no public AI services, CaseFlow is read-only, a person makes every decision, and every model call is logged. The 2024 pilot failed because it never showed how sure it was. The sample export is usable but not clean: 22.6% of asks and escalations have no reason code, 9.2% of file formats and 8.3% of dates are in the wrong format, and the analyst notes hold 37 undeclared personal-data values that the client must remove before we handle real data.

## Options considered

| | Option A | Option B | Option C |
|---|---|---|---|
| Summary | Vision model reads the page image (Claude Sonnet on Bedrock) | Textract OCR reads the words, Claude Haiku turns them into fields | Public document-AI service approves clean cases |
| Meets the client rules? | Yes, all 5 | Yes, all 5 | No: breaks 6 times (leaves the UK, public AI, writes to CaseFlow, model decides, no person decides, not logged) |
| Run-cost per month (GBP) | £401 at 8,600 docs; £474 at 17,200 | £422 at 8,600 docs; £439 at 17,200 | £211 at 8,600 docs; £305 at 17,200 |
| Time to first pilot | 3 weeks | 4 weeks | 1 week |
| Main risk | No word-level confidence or positions: we must build our own | One more service to run; weaker on photos and handwriting | Breaks the bank's rules, so not allowed |

## Decision

Option B. It meets every rule, and it gives a confidence and a position for each word, which answers F08 and F09. It is also cheaper than A at the January peak (£439 against £474). Option C is out because it breaks six rules.

## Consequences

- **Good:** doubtful fields can be boxed from real OCR confidence; cost per page is very low; each step can be checked separately.
- **Bad:** four weeks to a pilot, one more than A, and one more service to run; photos are weaker.
- **To watch:** if Textract in London reads blurred or photographed pages badly, A could win on accuracy. In the sample export, blur is a small share of coded reasons (6 of 127); the biggest is a proof of address older than 3 months (99), which no reader can fix. Also check the London Textract price (see `docs/PRICE_CHECK.md`).
