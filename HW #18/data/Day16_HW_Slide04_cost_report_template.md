# Cost report: IT policy chatbot

Name: ________________     Date: __________

Prices used (US dollars per million tokens; from OpenRouter on the date above):

| Model | Input | Output |
|---|---|---|
| anthropic/claude-haiku-4.5 | | |
| openai/gpt-4.1-mini | | |
| ollama/llama3.2:3b | 0 | 0 (but see "hidden costs") |

## 1. Load test results (scripts/compare_reports.py)

| | Baseline | Cache | Cache + routing |
|---|---|---|---|
| p50 seconds | | | |
| p95 seconds | | | |
| Cost per 1,000 questions (USD) | | | |
| Cache hit rate | | | |
| Share answered by the small model | | | |

## 2. Monthly cost at 10,000 questions a day (30 days), from monthly_cost()

| | Baseline | After my optimisations | Saving |
|---|---|---|---|
| Model bill per month (USD) | | | |

## 3. What if?

- Real users repeat themselves less than the load test does. With half your cache hit rate, the monthly cost is: ______
- Traffic doubles to 20,000 a day. The monthly cost is: ______ . Does the small model on one laptop keep up? (p95 at 8 users: ______ s)
- Hidden costs of the open model: the machine that runs it, keeping it updated, and someone on call for it. Rough monthly figure: ______

## 4. Quality

- scripts/quality_recheck.py with routing on: PASS / FAIL. Which checks failed, and on which route?
- One answer that got worse, quoted:

## 5. Decision (three sentences)

Which optimisations would you switch on in production, which not, and what would you watch on the dashboard to know you were right?
