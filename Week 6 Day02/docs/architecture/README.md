# Candidate architectures for UC1, the proof-of-address check

Each option is one JSON file here: `option_a.json`, `option_b.json`, `option_c.json`. The console draws it on the **Architectures** tab and checks it against the client's rules (ticket ENG-202).

## The format

Copy the shape of `option_a.json`.

- **nodes:** every box. Each one has:
  - `kind`: `person`, `ui`, `service`, `model`, `ocr`, `store`, `system`, `audit_log` or `decision`
  - `lane`: `client` (bank staff), `bank` (bank network, UK), `aws` (AWS London) or `external` (outside the bank)
  - `row`: its position from the top, starting at 0
  - `region`: where it runs, such as `uk` or `us`
  - `customer_data`: true if it holds or sees customer data
  - `hosting`: for models, `bedrock` or `public`
  - `read_only`: true for systems we may only read
- **edges:** every arrow, as `from`, `to` and a short `label` (one or two words).
- **cost:** what the run-cost tab needs.

## Option B · Parse, then reason (you write this one in Activity 2)

The same as Option A, except for how the page is read:

1. The check service sends the page image to **Textract OCR** in AWS London. It returns the words, with their positions on the page and a confidence for each.
2. The check service sends those words to **Claude Haiku on Bedrock** in AWS London, which turns them into the fields.

Everything else is unchanged:
- CaseFlow is read, never written.
- The check service sends fields and boxes to the review screen.
- The analyst decides.
- The model and the check service both log to the audit log.

| Field | Value |
|---|---|
| id, name | `B`, `Parse, then reason` |
| summary | OCR reads the words with their positions and confidence; a small model turns the text into fields. |
| time_to_pilot_weeks | 4 |
| strengths | Word-level confidence and positions from OCR: we can show where every answer came from · Very low cost per page |
| weaknesses | One more service to run · Weaker on photos and handwriting |
| cost | model `claude-haiku-5.5`, regional `true`, 1,200 input and 300 output tokens per page, ocr `true`, fixed USD 520 a month |
