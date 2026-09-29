# Model choice: which model for which task

Data: `data/benchmark.csv` (10 prompts x 3 models = 30 calls, one run, reply cap 600 tokens). Quality scores (1-5) were assigned by Claude, not by a human reviewer, on correctness, following the instruction as written, and format. The prompts are the ten course IT prompts, not prompts from my own work.

## Recommendation
Use `hosted` (claude-haiku-4.5) as the default for classification, extraction, summaries, commit messages and test-case drafts. Escalate to `strong` (claude-sonnet-4.5) for anything that needs reasoning about a rule or trade-off (the batch-window prompt is the one clear case in this data) and keep `local` only as the fallback when the hosted provider is unreachable.

## Evidence

| Backend | Model | Avg score (1-5) | Avg seconds | Cost, 10 prompts | Cost per call |
|---|---|---|---|---|---|
| hosted | anthropic/claude-haiku-4.5 | 4.1 | 1.89 | $0.0057 | $0.00057 |
| strong | anthropic/claude-sonnet-4.5 | 4.5 | 3.83 | $0.0187 | $0.00187 |
| local | llama3.2:3b (Ollama) | 2.8 | 7.97 (5.48 without the 30.4 s first call) | $0 | $0 |

What the scores show:
- `strong` beat `hosted` by 0.4 points on average. Its clearest win was prompt 4 (the 05:50 batch job that must not run after 06:00): strong 5 vs hosted 3. Both said "do not start", but hosted's reason was wrong (it said finishing at 06:15 was before the 06:30 report and treated the 06:00 rule as a "buffer"). Local said the job could run: 1.
- The two hosted models tied on prompt 3 (JSON extraction, 5 each) and were within 1 point on prompts 1, 2, 6, 7, 8 and 9.
- `hosted` scored higher than `strong` on prompt 5 (customer rewrite, 4 vs 3, because strong kept "As mentioned previously") and prompt 10 (test cases, 5 vs 3). The prompt 10 result is partly an artefact: strong's answer hit the 600-token cap and was cut off mid-step.
- `local` scored 3 or below on 7 of 10 prompts. It added unrequested fields and text on prompt 3, chatted around the answer on prompt 7, and wrote an incoherent test plan on prompt 10 (a JWT login step that does not fit a password reset).
- Speed: hosted was fastest at a mean 1.89 s, strong about twice as slow at 3.83 s.

Limits of this evidence: 10 prompts, one run each, a single scorer (not the user), a small quality gap between the hosted models (0.4). It supports "use the cheap model by default", not a precise ranking.

## Cost
Per-call costs from the benchmark, projected at an assumed 1,000 calls a day for 30 days (my team's real volume is not measured, so change the volume to your own):

| Plan | Monthly cost |
|---|---|
| All calls on `hosted` | about $17 |
| All calls on `strong` | about $56 |
| `hosted` default, 20% escalated to `strong` | about $25 |
| `local` | $0 in API fees (own hardware and time) |

`python -m scripts.cost_report` on the 9-call chat log in `data/usage.csv` gives higher figures ($35 and $95 a month) because those were longer chat replies. Output tokens made up 76% of the cost there, so asking for shorter answers may save as much as switching models.

## Risks
- **Privacy:** Prompts sent to `hosted` and `strong` leave the machine through OpenRouter. Redact names, customer data and internal identifiers before sending. Anything that cannot be redacted should go to `local`, whose quality here was the weakest.
- **Rate limits and credit:** OpenRouter returned HTTP 402 during this work because the account balance was too low for the default 64,000-token reply limit. Both the benchmark and the chatbot now send a `max_tokens` cap. `ask()` retries rate-limit errors and timeouts three times with a doubling wait.
- **Provider down:** `ask()` falls back to the `local` backend after the retries fail. `local` needs Ollama running with the model pulled (`llama3.2:3b`), and its answers were the weakest, so treat fallback answers as lower confidence.

## Review
Repeat the benchmark on ten of my own work prompts, scored by a person, by 2026-12-28, or sooner if OpenRouter prices change or a new model is released. This decision would change if the score gap between `hosted` and `strong` grows on real prompts, if the escalation rate goes well above 20%, or if `local` reaches a score of 4 on the tasks I need it for.
