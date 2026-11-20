# Batch report: the October batch through the pipeline

Run on: 2026-11-17 · Model: scripted (no real model was called) · Calls at once: 8 (16 tried and failed)

**Simulated:** every number below comes from the scripted model. Accuracy, routing, refusals, time and cost are measured on the bank's answers in Pipeline → Compare, Routing and Batch, but the times, the 429 refusals and the cost per document are simulated, not read from a real model.

## What ran

| | |
|---|---|
| Documents | 200: 120 bills, 80 bank statements |
| Files | 108 digital PDFs, 12 scanned PDFs, 80 JPG scans |
| Prompts | extract_v2 (parser + LLM) checked against extract_vlm_v1 (vision) |
| Routing | confidence below 0.85, and with agreement |

## Field-level accuracy

| Field | Parser + LLM | Vision model | After the Review queue |
|---|---|---|---|
| Full name | 98.5% | 99.0% | 100.0% |
| Address | 99.0% | 96.5% | 100.0% |
| Statement date | 86.0% | 91.5% | 98.5% |
| Issuer | 100.0% | 100.0% | 100.0% |
| **All fields** | 95.9% | 96.8% | 99.6% |
| One keyer at the bank today | | | 98.6% |

"After the Review queue" assumes the analyst fixes every field the routing sends them; the 3 errors that slip through (all statement dates) are the only ones left. The first vision prompt, extract_vlm_v0, scored 73.4% because it reformatted dates and addresses; extract_vlm_v1 copies values as printed.

## Throughput

| Calls at once | Finished | Refused (429) | Time | Documents a minute |
|---|---|---|---|---|
| 16 | 82 of 200 | 1,620 | 1.1 min | 77.0 |
| 8 | 200 of 200 | 0 | 1.6 min | 124.1 |

A month of documents (8,600) at the chosen setting (8 at once): 69 minutes. At 16 at once it would be 112 minutes, and only if every document were retried until it finished.

Twice the calls at once finished fewer documents a minute, because the refused calls are wasted.

## Cost and people

| | A document | A month |
|---|---|---|
| Model, class model (Haiku 5.5) | $0.00032 | £2 |
| Model, pilot (Sonnet 5 in London) | $0.00695 | £47 |
| Model, pilot as a batch job | $0.00348 | £23 |
| Fields a person handles: today | | 34,400 typed |
| Fields a person handles: with the pipeline | | 3,750 checked (31,545 → 30,650 go straight through) |

Fields checked: 87 of 800 in the October batch (10.9%), scaled to 8,600 documents a month. The pilot as a batch job costs half, with results within 24 hours; check that batch inference exists for this model in eu-west-2 first.

## What we do not know yet

The scripted model cannot tell us the real accuracy, the real latency, or where a real service starts refusing calls: the limit of 8 at once is a simulated one. The pilot must measure those on Sonnet 5 in London, on a fresh set of documents the prompts were not tuned on.
