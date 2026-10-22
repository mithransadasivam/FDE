# Why each threshold has this number

| Threshold | Value | Reason |
|---|---|---|
| min_hit_rate | 0.95 | Day 7 measured 100% with full mode on 20 questions (vector 90%). One question is 5 points, so 0.95 allows one miss for noise but fails a pipeline as weak as vector. |
| min_citation_pass_rate | 1.0 | A broken or missing citation is never acceptable: users cannot check the answer. |
| min_behaviour_rate | 0.9 | Task 1 measured 10/10 (7 answered, 3 declined correctly). One question is 10 points, so one miss is allowed. |
| min_judge_correct_rate | 0.9 | Task 1 measured 1.0, and the judge agreed with my labels 10/10. Allow one miss. |
| min_judge_grounded_rate | 0.9 | Task 1 measured 1.0; agreement 10/10. Allow one miss. The judge is less reliable on grounded (11/12 on the class sample, it accepted one uncited fact), so the code citation check backs it up. |
| max_avg_seconds | 15 | Task 1 measured 10.4 s per whole answer in full mode. RAG_DECISION_day07.md set a lenient 15 s limit for a chat (embedding alone takes about 2 s here). |
