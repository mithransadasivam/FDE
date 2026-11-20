# Batch report: the October batch through the pipeline

Run on: <date> · Model: <class model, or scripted> · Calls at once: <n>

## What ran

| | |
|---|---|
| Documents | <200: n bills, n bank statements> |
| Files | <n digital PDFs, n scanned PDFs, n JPG scans> |
| Prompts | <parser prompt> checked against <vision prompt> |
| Routing | confidence below <x>, and <with / without> agreement |

## Field-level accuracy

| Field | Parser + LLM | Vision model | After the Review queue |
|---|---|---|---|
| Full name | | | |
| Address | | | |
| Statement date | | | |
| Issuer | | | |
| **All fields** | | | |
| One keyer at the bank today | | | |

## Throughput

| Calls at once | Finished | Refused (429) | Time | Documents a minute |
|---|---|---|---|---|
| <n> | | | | |

A month of documents (8,600) at the chosen setting: <time>.

## Cost and people

| | A document | A month |
|---|---|---|
| Model, class model | | |
| Model, pilot (Sonnet 5 in London) | | |
| Model, pilot as a batch job | | |
| Fields a person handles: today | | |
| Fields a person handles: with the pipeline | | |

## What we do not know yet

<Two or three lines: what the scripted model cannot tell you, and what the pilot must measure.>
