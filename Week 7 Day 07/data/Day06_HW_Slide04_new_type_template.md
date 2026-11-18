# A new document type: council tax bills

Measured on: <date> · Model: <class model, or scripted> · Set: council_tax (20 documents)

## What the bank sent

| | |
|---|---|
| Documents | <n> council tax bills |
| Files | <n digital PDFs, n JPG scans, n PDFs with no text layer> |
| One keyer at the bank | <% of fields right> (keyer A <%>, keyer B <%>) |

## Field-level accuracy, before the fix

| Field | Parser + LLM (`extract_v2`) | Vision model (`extract_vlm_v1`) |
|---|---|---|
| Full name | | |
| Address | | |
| Statement date | | |
| Issuer | | |
| **All fields** | | |

What goes wrong, in one sentence, with two examples (document, what was read, the bank's answer):

<…>

## The fix

The prompt: `backend/app/prototype/prompts/<new prompt>.md`. What it adds, in one or two lines:

<…>

## After the fix, with the routing from ADR-003

| | Before (`extract_v2`) | After (`<new prompt>`) |
|---|---|---|
| Fields right, parser alone | | |
| Fields sent to a person | | |
| Errors that slip through | | |
| Right after the review (one keyer: …) | | |

Did the fix change the October batch? <yes / no, with its fields-right before and after>

## What we still do not know

<One or two lines.>
