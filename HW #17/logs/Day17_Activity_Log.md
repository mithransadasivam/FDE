# Day 17 Activity Log

Name: ________________

## Before we start (slide 5)
- Presidio installed and in requirements.txt: yes / no
- en_core_web_sm downloaded: yes / no
- test_service_parts_day17.py: __ / 10 passing
- CHAT_FAKE in .env for the activities: 1 / 0

## Activity 1: score the attacks, a baseline (slide 9)
- Scoring tests passing: __ / 7
- Baseline: ____ of 15 attacks worked (fake or real model: ______)
- Which attacks arrived through something the user never sees?
- Which attacks changed or deleted data?

## Activity 2: the input guardrail (slide 14)
- Input guardrail tests passing: __ / 7
- Chatbot attacks still working: ____ of 9. Which? __________
- Why did C04 stop at the document, and C05 on the way out?

## Activity 3: personal data (slide 20)
- PII tests passing: __ / 5
- C06: WORKED / stopped     A04: WORKED / stopped
- Which staff column did Presidio not hide? __________
- In A04, who still saw the home addresses?

## Activity 4: least privilege and regression tests (slide 25)
- Permission tests passing: __ / 6

| Run | Attacks that worked | Blocked by a guardrail |
|---|---|---|
| before | | |
| after (guardrails + least) | | |

- test_security_regression.py: __ / 3 passing
- e2e_security.py against the container: __ passed
- The attack that still works, and would you accept it? Why?

## Optional: the real model
- Baseline with CHAT_FAKE=0: ____ of 15 worked. Which did the model resist by itself?
