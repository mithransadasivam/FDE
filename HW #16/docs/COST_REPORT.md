# Cost report: IT policy chatbot

Name: Mithran Sadasivam     Date: 2026-10-20

Prices used (US dollars per million tokens; from OpenRouter, 2026-10-20):

| Model | Input | Output |
|---|---|---|
| deepseek/deepseek-chat (my main model) | 0.2574 | 1.0287 |
| anthropic/claude-haiku-4.5 | 1.00 | 5.00 |
| openai/gpt-4.1-mini (my fallback) | 0.40 | 1.60 |
| ollama/llama3.2:3b | 0 | 0 (but see "hidden costs") |

## 1. Load test results (scripts/compare_reports.py)

60 questions, 4 users at a time, real model. I ran each one once. A few requests failed with OpenRouter 504 timeouts (4, 2 and 2 out of 60), so treat the p95 numbers as rough.

| | Baseline | Cache | Cache + routing |
|---|---|---|---|
| p50 seconds | 6.86 | 0.13 | 0.19 |
| p95 seconds | 23.2 | 52.8 | 52.3 |
| Cost per 1,000 questions (USD) | 0.2055 | 0.0687 | 0.0205 |
| Cache hit rate | 0% | 67% | 66% |
| Share answered by the small model | 0% | 0% | 22% (13 of 60) |

The p95 got worse, not better. The cache makes repeats instant, but the questions that miss still have to go to the model, and a couple of those hit slow OpenRouter calls of about 50 seconds. The cache fixes the typical question, not the worst one.

## 2. Monthly cost at 10,000 questions a day (30 days), from monthly_cost()

| | Baseline | After my optimisations | Saving |
|---|---|---|---|
| Model bill per month (USD), cache only | 61.65 | 20.61 | 41.04 (67%) |
| Model bill per month (USD), cache + routing | 61.65 | 6.15 | 55.50 (90%) |

At 20,000 a day the same three bills are $123.30, $41.22 and $12.30.

## 3. What if?

- Real users repeat themselves less than the load test does. With half the cache hit rate (about 34% instead of 67%), the cache-only bill is about $41.70 a month, instead of $20.61. Still a third cheaper than no cache.
- Traffic doubles to 20,000 a day. The bill is $41.22 with the cache and $12.30 with cache + routing. Does the small model on one laptop keep up? No. My routing test run averaged 61 seconds an answer while the laptop was also busy with other work, so I would not put more load on it.
- Hidden costs of the open model: the machine that runs it, keeping it updated, and someone on call for it. A small GPU server is roughly $300-600 a month, which is far more than the $55 a month routing saves. At this volume the laptop model costs more than it saves.

## 4. Quality

- scripts/quality_recheck.py with routing on: **FAIL**. Four checks passed (citations 1.0, behaviour 1.0, judge correct 0.83, judge grounded 0.83). It failed on average time: 61.4 s against a limit of 6 s.
- Answers that got worse, both on the small model: "What is the response target for a P1 incident?" said 4 hours, but the source says 15 minutes (it mixed up response and resolution times). "How often are laptops replaced?" added an extra claim about replacing them early if they fail.
- The cache on its own does not touch quality, because a cached answer is a copy of an earlier answer from the same model.

## 5. Decision (three sentences)

Switch the response cache on now: it cuts the bill by about two thirds, answers repeats in a fraction of a second, and only needs to be cleared when the policies or the prompt change. Do not turn routing on: it saves another $14 a month but gave a wrong P1 response time, which is exactly the kind of answer people act on, and it failed the speed check. On the dashboard I would watch cache hit rate, cost per 1,000 and p95 for two weeks, and only revisit routing with a stronger small model and a clean quality check.

## 6. Would a semantic cache be safe? (Task 3)

I added two pairs of my own: "idle timeout vs maximum length of a VPN session" (different answers) and "read company email on my personal phone vs use my own phone for company email" (same answer).

Highest scoring pair: 0.941, "How long can a VPN session stay connected?" against "how long does the vpn stay connected", which really is the same question. The highest-scoring *wrong* pairs were Confidential vs Public email (0.926) and P1 vs P2 response target (0.917).

| Threshold | Right hits | Wrong hits | Missed |
|---|---|---|---|
| 0.80 | 5 | 5 | 2 |
| 0.85 | 4 | 4 | 3 |
| 0.90 | 1 | 2 | 6 |
| 0.95 | 0 | 0 | 7 |
| 0.98 | 0 | 0 | 7 |

Do not ship it. The only threshold with no wrong hits (0.95) also has no right hits, and anything lower hands someone the wrong policy answer (P2 instead of P1, Public instead of Confidential). A single changed word flips the answer but hardly moves the embedding score. The exact-match cache already gets the repeats safely.
