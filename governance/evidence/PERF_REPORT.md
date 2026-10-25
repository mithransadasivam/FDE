# PERF_REPORT: cost and speed, before and after Part 2

Load test: **60 questions** drawn from `data/operator_questions.csv` by weight, **4 users at once**, seed **17** (two runs with the same seed ask the same questions in the same order). Measured over HTTP against the running API.

## Fake model with a latency profile (reproducible, free)

The fake model sleeps a fixed time per call (0.45 s + tokens for the large model, 0.12 s + tokens for the small one) and reports token counts estimated from text length. Prices are those configured for the real models, so the cost column is an estimate; the speed column shows what the routing and the cache change, not what a provider's latency would be.

| Run | p50 | p95 | Throughput | Cost per 1,000 questions | Cache hit rate | Errors |
|---|---|---|---|---|---|---|
| baseline (routing off, cache off) | 1.13 s | 1.49 s | 3.37 q/s | $1.12 | 0% | 0 |
| after (routing on, cache on) | 0.09 s | 1.20 s | 10.23 q/s | $0.11 | 50% | 0 |

**Change:** p50 -92%, p95 -19%, cost per 1,000 -90%, throughput +204%.

- **baseline** · where the questions went: large 60 · p50 by route: large 1.08 s · same first five questions: yes

- **after** · where the questions went: cache 16, data 28, large 6, small 10 · p50 by route: cache 0.01 s, data 0.04 s, large 1.11 s, small 0.84 s · same first five questions: yes

**Streaming (after):** the model's first token arrives at p50 0.10 s; the first text a person can read (after the sentence-level output check) at p50 0.28 s, against 0.73 s for the whole answer (10 model-routed questions).

**Cost per incident brief:** $0.0011 (investigator + planner + scribe calls, averaged over 8 briefs; triage of all 22 alerts took 16.6 s).

## Real models through OpenRouter

Large model `anthropic/claude-haiku-4.5`, small model `meta-llama/llama-3.1-8b-instruct`.

| Run | p50 | p95 | Throughput | Cost per 1,000 questions | Cache hit rate | Errors |
|---|---|---|---|---|---|---|
| baseline (routing off, cache off) | 1.99 s | 3.46 s | 1.75 q/s | $1.00 | 0% | 0 |
| after (routing on, cache on) | 0.07 s | 3.24 s | 5.45 q/s | $0.11 | 46% | 0 |

**Change:** p50 -97%, p95 -6%, cost per 1,000 -89%, throughput +211%.

- **baseline** · where the questions went: large 60 · p50 by route: large 1.93 s · same first five questions: yes

- **after** · where the questions went: cache 12, data 34, large 6, small 8 · p50 by route: cache 0.01 s, data 0.02 s, large 2.06 s, small 2.40 s · same first five questions: yes

**Streaming (after):** the model's first token arrives at p50 0.90 s; the first text a person can read (after the sentence-level output check) at p50 1.41 s, against 1.69 s for the whole answer (9 model-routed questions).

**Cost per incident brief:** $0.0020 (investigator + planner + scribe calls, averaged over 8 briefs; triage of all 22 alerts took 72.7 s).

## Did the answers get worse? Ten answers before and after

Each question has facts the answer must contain. Model: **real**. Before = routing off, cache off; after = routing on, cache on.

| # | Question | Before | After | Route after |
|---|---|---|---|---|
| 1 | What is the status of the Payment Portal? | 0/2 | 2/2 | data |
| 2 | Which incidents are open right now? | 0/2 | 2/2 | data |
| 3 | Who owns the Core Database? | 1/2 | 2/2 | data |
| 4 | Which services depend on db-core? | 3/3 | 3/3 | data |
| 5 | What does runbook RB-04 say to do first? | 1/1 | 1/1 | small |
| 6 | Which steps in RB-07 need approval? | 2/2 | 2/2 | data |
| 7 | When does the change freeze start and end? | 2/2 | 2/2 | data |
| 8 | What makes an incident P1? | 2/2 | 2/2 | small |
| 9 | Which team is on call for Identity? | 1/1 | 1/1 | data |
| 10 | How do I fail over the core database? | 2/2 | 2/2 | small |

**Total:** before 14/19 facts, after 19/19 facts. No answer got worse.

**What this check caught.** The first time it ran with the real models it found one answer that got worse: *Which steps in RB-07 need approval?* scored 2/2 on the large model and 0/2 on the small one (`llama-3.1-8b-instruct` said "steps 2 and 3"; it is 3 and 4). The question is a filter over parsed runbook steps, so a model can only add mistakes. It now goes to the **data route** (exact, no model, free), and the check passes. That is the answer to "which questions are safe without a model": those whose answer is a row, a count or a filter in our own tables.

## How to reproduce

```
python -m scripts.loadtest --label baseline --routing off --cache off
python -m scripts.loadtest --label after --routing on --cache on
python -m scripts.answer_check
python -m scripts.loadtest --report
```
