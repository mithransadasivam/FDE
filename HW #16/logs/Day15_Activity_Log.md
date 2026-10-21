# Day 15 Activity Log

Name: Sadasivam Mithran

## Before we start (slide 5)
- New libraries installed and in requirements.txt: yes
- OLLAMA_URL read in app/embeddings.py: yes
- Docker version: 29.9.1   Images pulled (python:3.12-slim, Phoenix): yes

## Activity 1: the /ask endpoint
- API tests passing: 5 / 5

## Activity 2: readiness and the container
- Readiness tests passing: 5 / 5
- /ready with Ollama running: ready true (api_key, index 62 chunks, ollama all ok)

## Activity 3: tracing
- Tracing tests passing: 5 / 5

## Activity 4: retries and a fallback
- Reliability tests passing: 8 / 8

| Run | Answered | Failed | By the fallback | p95 seconds (dashboard) |
|---|---|---|---|---|
| Outage of the primary model (fake chatbot, 20 requests) | 20 | 0 | 14 | 2.153 |
| Every model down (fake chatbot, 20 requests) | 6 (declines only) | 14 | 0 | 0.001 |
| Normal again (real models, 10 requests) | 10 | 0 | 0 | 6.049 |

- What would you want to be told, and when, if this happened at 3 a.m.? See docs/RUNBOOK.md: the fallback alert fires first (users still served), the error alert when users start getting 503.

## Homework (HW 15)
- Task 1: check_alerts() written, tests/test_alerts.py 5 / 5. Full suite 348 passed.
- Task 2: four rules in data/Day15_HW_Slide03_alert_rules.json; drills in logs/drill1_metrics.json and logs/drill2_metrics.json.
- Task 3: docs/RUNBOOK.md.
