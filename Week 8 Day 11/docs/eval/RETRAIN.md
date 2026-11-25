# Retraining for council tax bills

**Model before:** small-1 (trained on the pilot's reads)  ·  **Model after:** small-2 (pilot + council_tax)  ·  **Threshold:** 0.70  ·  **Date:** 2026-11-25

All numbers come from the Model lab (New document type / drift, and the Models table) on the scripted model, which plays Sonnet as it did on Day 6. Every score compares with Tom's double-keyed labels, never with the teacher.

## What happened when council tax bills arrived

The 20 keyed council tax bills went through small-1 at a threshold of 0.70:

- **Small model alone: 75.0%** of fields right (60 of 80).
- **Sent to the pilot: 100%** (20 of 20). Every one has the same reason: **statement_date missing**.
- **Errors that slip through: 3.** These are the pilot's own errors (small-1 let none through itself).

Why: small-1 was trained only on bills and bank statements. It has never seen a council tax bill, so it cannot find the statement date on one: no word gets that label, the field comes out empty with confidence 0, and the cascade does the safe thing and sends the document to the pilot. The cascade was safe, but not free.

`retrain_candidates()` shows it plainly, per kind:

| Kind | To the pilot | Share | Retrain? |
|---|---|---|---|
| bank_statement | 24 of 80 | 30.0% | no |
| council_tax | 20 of 20 | 100.0% | **yes, top reason statement_date** |
| utility_bill | 15 of 120 | 12.5% | no |

(Spot checks are not counted: those documents were sure.)

**What it costs.** Every council tax bill is two Sonnet calls (about $0.0069, £0.0054 at 0.78) and about 2 seconds at the counter (p50 1,997 ms against 5 ms for the small model). Per 1,000 council tax bills that is 2,000 Sonnet calls, about £5.41, and about 33 minutes of counter waiting. The Model lab does not hold the bank's number of council tax bills (Martin's volumes file gives only 8,600 documents a month in total), so I have not put a monthly figure on it. Even if every one of the 8,600 were a council tax bill, the model bill would be about £47 a month: the real cost is the 2 seconds at the counter, for as long as nobody notices.

## What the retrain used

small-2 was trained on **1,800 reads: the pilot's 1,500 plus the 300 council tax reads**. **1,396 were kept and 404 left out** (1,153 of the pilot's 1,500, and **243 of the 300 council tax reads**).

A read is left out when the pilot's two readings (parser and vision) disagree on any field, or the parser cites no words (ENG-1101, CLAUDE.md rule 20). Of the **57 council tax reads left out**, 51 disagreed on **statement_date** and 7 on **address** (one read disagreed on both). The statement date is the same trap as on bank statements: a council tax bill lists ten instalment dates, and the pilot sometimes reads one of those as the date of issue, while its second reading does not. Training on those would teach the small model the pilot's mistake, so they stay out.

## Before and after

| | Before (small-1) | After (small-2) |
|---|---|---|
| Council tax: small model alone | 75.0% | **100.0%** |
| Council tax: sent to the pilot | 100% (20 of 20) | **10%** (2 of 20, both spot checks) |
| Council tax: errors that slip through | 3 | **0** |
| October: small model alone | 98.2% | **98.2%** |
| October: sent to the pilot | 26.0% (39 of 200) | **21.5%** (30 of 200) |
| October: errors that slip through | 2 | **2** |

For October the pilot alone lets **3** errors through. Counting the spot checks too, the cascade sends 13 more October documents to the pilot, as before the retrain. October's small-model errors that slipped through the cascade without a person or the pilot seeing them: **0** both times.

## Is the new model safe to roll out?

**Yes: small-2 passes CLAUDE.md rule 20.** On the October batch the cascade at 0.70 lets through **2 errors, no more than the pilot's 3**, and that is the same 2 as before the retrain. October is the release condition, and it did not move: 98.2% alone before and after, 2 slipped before and after, and the share going to the pilot fell from 26.0% to 21.5%. Nothing on October got worse. The model file holds weights only, no customer data.

What did change: council tax went from 100% to the pilot to 2 spot checks, and from 3 errors to 0.

Caveats, so nobody over-reads this:

- Council tax is **20 keyed bills**. 100% on 80 fields is encouraging, but a small set.
- The retrain left out 57 of the 300 council tax reads, all ones the pilot itself was not sure of. Most of them (51) are the reads where the pilot reads an instalment date as the date of issue, so the small model has not been taught them, and still has to meet them.
- The ADR-008 entry for the new model (rule 20) is still to be written with the team: this report is its evidence.

## What we would watch next

1. **Council tax spot checks for a month.** Two of 20 bills are spot-checked. If the small model and the pilot disagree on any of them, or `retrain_candidates()` shows council_tax above 50% to the pilot again, that is the first sign of drift. March is the one to watch: the new tax year's instalment dates arrive and the layout of the instalment table may change.
2. **statement_date on every kind.** It is the top reason on bank statements (16 of 80 to the pilot) and utility bills (14 of 120) after the retrain, and the field where the pilot disagrees with itself. Re-run the October batch before any new model or threshold goes live, and again when the pilot's own model is upgraded next month (the teacher's reads would change, and so what the retrain keeps).
