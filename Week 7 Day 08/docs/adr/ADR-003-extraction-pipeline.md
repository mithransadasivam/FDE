# ADR-003: Read documents with a parser, checked by a vision model

- **Status:** accepted
- **Date:** Day 6 of the engagement
- **Deciders:** Deborah (the Review queue), Helen (the rules), Martin (the cost)
- **Builds on:** ADR-001 (grounded extraction), ADR-002 (the pilot platform)

## Context

The October batch has 200 documents: 120 PDFs and 80 JPG scans, read as 108 from a text layer and 92 from the bank's OCR (12 are PDFs with no text layer). One keyer at the bank gets 98.6% of the 800 fields right (keyer A 98.8%, keyer B 98.4%, the two agree on 97.1%). The bank handles about 8,600 documents a month, and today a person types all 34,400 fields. Results below are from Pipeline → Compare and Routing, on the scripted model.

## Options considered

| | Option A · parser + LLM, confidence routing | Option B · parser + LLM, checked by a vision model | Option C · vision model only |
|---|---|---|---|
| Fields right before review | 95.9% | 95.9% (vision 96.8%) | 96.8% |
| Fields sent to a person | 6.8% | 10.9% | 7.4% |
| Errors that slip through | 20 of 800 | 3 of 800 | 15 of 800 |
| Right after the review (one keyer today: 98.6%) | 97.5% | 99.6% | 98.1% |
| Model cost a month (GBP, pilot model, 8,600 documents) | £20 | £47 (£23 as a batch job) | £27 |
| Main risk | Confident wrong dates go straight through | Costs two calls a document | A value the page does not print is trusted |

## Decision

Option B: read every document with `extract_v2` on the parsed words, check every field against `extract_vlm_v1` on the picture of the page, and send a field to the Review queue when its OCR confidence is below 0.85 or the two methods disagree.

**Errors that slip through (Deborah and Tom):** 3 instead of 20. After the review, 99.6% of fields are right, better than one keyer (98.6%), and the analysts check about 3,750 fields a month instead of typing 34,400.

**Every auto-accepted value is printed on the page (Helen):** a field goes straight through only when the parser cites its words on the page with confidence 0.85 or more, and a second method reads the same value. A person decides everything else, and the UK rule from ADR-002 still holds: in the pilot, every call goes to Claude Sonnet 5 in London.

**Cost (Martin):** two model calls per document cost about £47 a month on the pilot model in London, or about £23 as a batch job, which is small beside the cost of typing 34,400 fields.

Also decided:
- **Vision prompt:** `extract_vlm_v1`. The first one, `extract_vlm_v0`, asked the model to tidy dates and addresses, so its values were not printed on the page: 73.4% right, against 96.8% for v1, which copies values as printed.
- **Confidence threshold:** 0.85. Raising it sends more fields to a person for little gain, because agreement already catches the confident mistakes.
- **Running the month:** 8 calls at once (more brings 429 refusals), as a nightly batch that is resumed for documents that fail, never skipped.

## New document type: council tax bills

**Before:** the 20 council tax bills were added as their own document set. `extract_v2` read the statement date wrongly on 8 of 20 bills (60.0%), because it took the first instalment date, "1 April 2026"; the vision model did the same on 5 (75.0%). After the review the set was 96.2% right, below one keyer on this set (98.1%), with 3 errors slipping through.

**Change:** `extract_v2` became `extract_v3`: one rule for council tax bills (the statement date is the date beside "Date of issue"; ignore the charge period and the instalment dates). `extract_v2` is unchanged. October still reads 95.9% with `extract_v3`, the same as with `extract_v2`.

**Result:** 98.8% right after the review, above one keyer (98.1%), with 5.0% of fields sent to a person and 1 error slipping through (C-002, where both methods read "1 April 2026"). The Decision above is unchanged: this section adds evidence.

**Rule for the next document type:** every new type is added as its own set with the bank's double-keyed sample (two analysts key a sample of each new type, because that is the only way to know the bar), measured field by field on both methods, and it goes live only when it beats one keyer after the review, on its own set. Fix what breaks with a new prompt file, never by editing the old one, and check that the other sets still read the same. The type gets its own section in this ADR.

## Consequences

- **Good:** most fields go straight through with a printed source, and the errors that slip through fall far below one keyer's.
- **Bad:** every document is read twice, and a person still checks about one field in nine.
- **To watch:** the errors agreement cannot catch (both methods wrong together, as with C-002); find them by sampling the auto-accepted fields each month against a double-keyed sample.
