# A new document type: council tax bills

Measured on: 2026-11-16 · Model: scripted (class model price: anthropic/claude-haiku-5.5) · Set: council_tax (20 documents)

All numbers are from Pipeline (Parse, Compare, Routing) on the council_tax set; the October check is from the october set.

## What the bank sent

| | |
|---|---|
| Documents | 20 council tax bills |
| Files | 12 digital PDFs, 8 JPG scans, 0 PDFs with no text layer (12 read from the text layer, 8 from the bank's OCR) |
| One keyer at the bank | 98.1% of fields right (keyer A 97.5%, keyer B 98.8%); the two agree on 96.2%, Tom settled 3 fields |

## Field-level accuracy, before the fix

| Field | Parser + LLM (`extract_v2`) | Vision model (`extract_vlm_v1`) |
|---|---|---|
| Full name | 100.0% | 100.0% |
| Address | 100.0% | 100.0% |
| Statement date | **60.0%** | **75.0%** |
| Issuer | 100.0% | 100.0% |
| **All fields** | 90.0% | 93.8% |

What goes wrong, in one sentence: a council tax bill prints the date of issue once and then a charge period and ten instalment dates, and `extract_v2` (and the vision model) take the first instalment / start of the charge period, "1 April 2026", as the statement date; both are below one keyer (98.1%).

Examples (document, what was read, the bank's answer):

- C-002: read "1 April 2026", the bank's answer is "09 Mar 2026"
- C-003: read "1 April 2026", the bank's answer is "06 Mar 2026"

`extract_v2` made 8 errors on 80 fields, all of them statement date (C-002, C-003, C-004, C-006, C-009, C-015, C-016, C-018).

## The fix

The prompt: `backend/app/prototype/prompts/extract_v3.md`. It is `extract_v2` unchanged plus one rule: on a council tax bill the statement date is the date beside "Date of issue"; ignore the charge period and every date in the instalment table, even when an instalment date comes first in reading order. `extract_v2` is not touched.

## After the fix, with the routing from ADR-003

Routing: confidence at 0.85, plus agreement with `extract_vlm_v1`.

| | Before (`extract_v2`) | After (`extract_v3`) |
|---|---|---|
| Fields right, parser alone | 90.0% | 98.8% |
| Fields sent to a person | 8.8% (7 of 80) | 5.0% (4 of 80) |
| Errors that slip through | 3 | 1 |
| Right after the review (one keyer: 98.1%) | 96.2% | 98.8% |

Statement date alone: 60.0% to 95.0% for the parser. The one error left is C-002: both methods read "1 April 2026" (bank's answer "09 Mar 2026"), so agreement cannot catch it.

Did the fix change the October batch? No. `extract_v3` reads October at 95.9% fields right, the same as `extract_v2` (95.9%); routing on October is the same too (87 fields to a person, 3 slip through, 99.6% after review).

## What we still do not know

These numbers come from the scripted model, so a real model will differ in size, though the failing field and the reason should not. Twenty bills is a small sample: one error is 1.25 points, and bills from other councils may print the issue date under another label.
