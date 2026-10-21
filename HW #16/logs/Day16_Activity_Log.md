# Day 16 Activity Log

Name: ________________

## Before we start (slide 5)
- llama3.2:3b pulled (`ollama list`): yes / no
- cache/ and logs/load_*.json in .gitignore: yes / no
- GET /ready after the rebuild: ready true / false

## Activity 1: price every answer, and a baseline (slide 9)
- Cost tests passing: __ / 5
- Price of one answer with 1,500 input and 150 output tokens on haiku-4.5: $________

| Load test | p50 s | p95 s | Questions a second | Cost per 1,000 | Tokens a question | Cache hit rate |
|---|---|---|---|---|---|---|
| baseline | | | | | | |
| cache | | | | | | |
| after (cache + routing) | | | | | | |

## Activity 2: the response cache (slide 14)
- Cache tests passing: __ / 5
- Why is p95 hardly lower when p50 falls to almost nothing?
- When must the cache be cleared?

## Activity 3: an open model (slide 20)
- measure_stream tests passing: __ / 5

| Model | First token s | Whole answer s | Tokens a second | Cost per 1,000 | Citation pass rate |
|---|---|---|---|---|---|
| hosted | | | | | |
| llama3.2:3b | | | | | |

- One answer pair where the two models differ most, and how:

## Activity 4: routing, and a quality re-check (slide 25)
- Router tests passing: __ / 7
- Share of questions on the small route: ______  Reasons seen most often: ____________
- quality_recheck.py: PASS / FAIL   Which metric failed, if any: ____________
- Your decision: switch on the cache? yes / no   Switch on routing? yes / no   Why:
