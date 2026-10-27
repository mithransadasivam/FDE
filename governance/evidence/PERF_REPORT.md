# PERF_REPORT.md

Generated 2026-10-27 by `python -m scripts.run_perf` from `evidence/perf.json`.

> **Read this first.** This run used **fake models**, so no model was called. Token counts are estimated (characters / 4) and are real for the prompts the platform builds; **costs are what those tokens would cost at the list prices** in `app/ai/router.py`; **model and speech latency are assumptions** (below). The platform's own compute time is measured. Run with `FAKE_MODELS=0` and replace the constants for figures you can quote.

## Cost (for 52 CVs and 5 AI interviews)

| What | Before | After | Change |
|---|---|---|---|
| Cost per 100 CVs screened (read + score) | $0.246 | **$0.1015** | routing: extraction moves to the local model, scoring stays on the large model |
| Cost per 100 CVs if extraction used the small hosted model instead | $0.246 | $0.1137 | not chosen: CVs carry identity, so extraction stays local (rule 10) |
| Cost per AI interview (LLM scoring) | $0.00383 | $0.00383 | scoring needs judgement, so it stays on the large model |
| Cost per AI interview (speech to text, assumed $0.006/min) | | $0.0176 | |
| Cost per AI interview (text to speech, assumed $0.015/1k chars) | | $0.0192 | |
| **Cost per AI interview, total** | | **$0.04063** | |

Tokens in the screening run: 38,215 in, 17,940 out (29,425 for reading CVs, 26,730 for scoring).

## Routing: small model for extraction and point-ticking, large for scoring and suggestions, local for any step that sees identity

Before: every call goes to the large model. After: `app/ai/router.py` sends each kind of step to the right tier, and a step that sees identity (reading a CV, drafting to a named person) never leaves the machine. The routing is also a privacy control, not only a cost one.

## Caching

| Test | Without cache | With cache |
|---|---|---|
| 15 assistant questions (5 questions asked 3 times): paid model calls | 15 | **5** |
| ...cost | $0.01632 | $0.00544 |
| ...CV search index builds (hiding identity + vectors) | 12 | **1** |
| ...time | 39.373 s | 3.191 s |
| Screening the same pool a second time: paid calls | 5 | 0 (5 served from cache) |

The model cache is keyed on the model, the prompt and the schema, so a changed CV or rubric never gets a stale answer. The assistant cache is also keyed on the size of the candidate pool.

## Speed

- Reading 52 CVs (PDF, Word, scans, screenshots, including OCR): **31.2 s**. Scoring them: **5.89 s**. (Days to minutes: the brief's first objective.)
- A whole 8-question AI interview from recorded answers: 0.082 s of platform compute.

## Voice interview speed

Target: the next question starts within **2.5 s at p95** after the candidate finishes.

| Part | Time | Source |
|---|---|---|
| The platform's own work per turn (read the answer, score it, choose the next question, save state), p95 | 3.35 ms | **measured** over 46 turns |
| Speech to text | 0.35 s | assumption |
| Scoring model call | 1.1 s | assumption |
| Text to speech, first audio | 0.4 s | assumption |
| Network margin | 0.3 s | assumption |
| **Estimated p95** | **2.15 s** | meets the 2.5 s target |

Because the three model/speech numbers are assumptions, this is an estimate, not a measurement. To measure for real, run the interview with real models and read the `latency_ms` column of the model-call ledger and the interviewer spans in the traces (Phoenix, or the Trust & cost tab).
