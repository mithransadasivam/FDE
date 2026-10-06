# Day 7 Homework: Choose a retrieval pipeline for your own documents

Mithran Sadasivam. Documents: 23 fictional Northwind IT documents (collection `my_docs`, 62 chunks).

## 1. Test set (20 questions)

File: `data/my_retrieval_test_set.csv` (6 plain, 4 reworded, 4 exact code, 3 follow-up, 3 messy).

```
Checked 20 questions against data/my_docs
  OK    How do I set up MFA on a new phone?
  OK    How long do you keep daily server backups?
  OK    My VPN keeps cutting out at home. What can I try?
  OK    What laptop does a new starter get?
  OK    I forgot my password and cannot sign in. What do I do?
  OK    How big a file can I email to a colleague?
  OK    How early should I refresh the security certificate on my wo
  OK    If I accidentally delete a document, how long can I get it b
  OK    Am I allowed to paste customer information into a public cha
  OK    What should I do if my laptop's battery looks puffed up?
  OK    What does error VPN-809 mean?
  OK    How do I fix NET-2240?
  OK    I keep getting WIFI-117, what now?
  OK    What is VPN-820?
  OK    How do I fix that if I'm not in the office?
  OK    And for P3?
  OK    What if I lose the phone instead?
  OK    hey, quick one, i've had my laptop forever and it's slow lol
  OK    hello, i'm stuck at an airport hotel and the vpn just wont c
  OK    Morning! got a weird email asking me to confirm my password,

20 of 20 evidence phrases found.
```

| # | kind | question | previous question | expected source | evidence |
|---|---|---|---|---|---|
| 1 | plain | How do I set up MFA on a new phone? |  | mfa_setup_guide.md | install Northwind Authenticator from the App Store |
| 2 | plain | How long do you keep daily server backups? |  | backup_and_recovery_runbook.md | kept for 30 days |
| 3 | plain | My VPN keeps cutting out at home. What can I try? |  | vpn_troubleshooting.md | Switch the protocol in NorthLink settings |
| 4 | plain | What laptop does a new starter get? |  | new_starter_checklist.md | 14-inch standard laptop, a headset |
| 5 | plain | I forgot my password and cannot sign in. What do I do? |  | password_policy.md | self-service page at reset.northwind.example |
| 6 | plain | How big a file can I email to a colleague? |  | email_and_calendar_faq.md | 25 MB. For larger files |
| 7 | reworded | How early should I refresh the security certificate on my work laptop for remote access? |  | Day06_Slide15_policy_vpn_remote_access.pdf | at least 14 days before it expires |
| 8 | reworded | If I accidentally delete a document, how long can I get it back? |  | file_sharing_and_storage.md | stay in the recycle bin for 93 days |
| 9 | reworded | Am I allowed to paste customer information into a public chatbot? |  | Day06_Slide15_policy_data_handling.pdf | must never be pasted into public AI tools |
| 10 | reworded | What should I do if my laptop's battery looks puffed up? |  | Day06_Slide15_policy_equipment_and_use.pdf | stop using the laptop immediately |
| 11 | exact code | What does error VPN-809 mean? |  | Day07_Slide05_kb_error_codes.pdf | VPN certificate on this laptop has expired |
| 12 | exact code | How do I fix NET-2240? |  | Day07_Slide05_kb_error_codes.pdf | run ipconfig /flushdns from a command prompt |
| 13 | exact code | I keep getting WIFI-117, what now? |  | Day07_Slide05_kb_error_codes.pdf | Guest Wi-Fi access lasts 8 hours |
| 14 | exact code | What is VPN-820? |  | Day07_Slide05_kb_error_codes.pdf | endpoint agent on this device is missing or not reporting as healthy |
| 15 | follow-up | How do I fix that if I'm not in the office? | What does error VPN-809 mean? | Day07_Slide05_kb_error_codes.pdf | call the service desk to renew it remotely |
| 16 | follow-up | And for P3? | What is the first response time for a P1 ticket? | Day06_Slide15_policy_it_support_slas.pdf | P3: response within 4 hours |
| 17 | follow-up | What if I lose the phone instead? | How do I set up MFA on a new phone? | mfa_setup_guide.md | Call the service desk on extension 4357 straight away |
| 18 | messy | hey, quick one, i've had my laptop forever and it's slow lol. is there like a schedule for swapping them out, and does IT warn me first?? |  | laptop_standards.md | about 2 months before your replacement |
| 19 | messy | hello, i'm stuck at an airport hotel and the vpn just wont connect, says cannot reach server or something, any ideas thanks |  | vpn_troubleshooting.md | firewall or hotel/airport network is blocking the VPN |
| 20 | messy | Morning! got a weird email asking me to confirm my password, i did click the link already, panicking a bit, what do i do? |  | phishing_and_security_reporting.md | If you already clicked a link or entered your password |

## 2. Comparison of the four pipelines

```
mode      hit@4   MRR        plain   reworded exact code  follow-up      messy     ms  calls
vector      90%  0.81          6/6        4/4        4/4        1/3        3/3   2154      0
hybrid      90%  0.70          5/6        4/4        4/4        2/3        3/3   2939      0
rerank      95%  0.83          6/6        4/4        4/4        2/3        3/3   6817      1
full       100%  0.77          6/6        4/4        4/4        3/3        3/3  11699      2
```

Best mode per kind: plain, vector and rerank/full (6/6; hybrid dropped one: "What laptop does a new starter get?"); reworded, exact code and messy, all four modes tie; follow-up, full (3/3), because it rewrites the question using the previous one.
Full mode (run on its own with `eval_retrieval --mode full`) still missed **no** questions: 20 of 20 found.
Hybrid helped follow-up "And for P3?" (keyword P3) but lost "What laptop does a new starter get?". Rerank gave the best MRR (0.83) at one extra model call. Full is the slowest and has a lower MRR than rerank, but is the only mode to find every question.

## 3. Diagnosis: two questions that vector mode missed
No question was missed in full mode, so I took the two that vector mode missed (output in `logs/explain_output.txt`).

**"And for P3?"** (previous: "What is the first response time for a P1 ticket?")
Vector found the SLA policy's page 1 and the service desk table, but not page 2, where "P3: response within 4 hours" is written. Hybrid, rerank and full all found page 2 (ranks 4, 3 and 3). Cause: the question needed context. "And for P3?" alone says nothing about response times. Fix: rewriting (full searched for "What is the first response time for a P3 ticket?").

**"How do I fix that if I'm not in the office?"** (previous: "What does error VPN-809 mean?")
Vector, hybrid and rerank returned printer, Wi-Fi and email text: "that" and "the office" carry no topic. Only full mode, which rewrote it as "How to fix error VPN-809 remotely not in office", found the error-code chunk saying "call the service desk to renew it remotely" (rank 3 in the full evaluation run, rank 1 when I ran explain_question; the reranker gives slightly different scores from run to run). Cause: the question needed context. Fix: rewriting. Side finding: the reranker scored that correct chunk only 1/10 because the chunk starts in the middle of the VPN-806 entry, so reranking can hurt when a chunk begins mid-topic.

## 4. Decision
See `RAG_DECISION_day07.md` (included below).

# Decision: retrieval pipeline for the Northwind IT help desk chatbot

## Context
23 fictional Northwind IT documents (62 chunks): policies (PDF), guides and FAQs (Markdown), and an error-code reference.
Asked by Northwind staff with everyday IT problems, often as chat follow-ups ("And for P3?").
Target: hit rate >= 95% at 4 chunks, with every kind of question answerable, and retrieval within 15 seconds on this laptop.
(The 15 s limit is lenient on purpose: embedding alone takes about 2 s here, and the chatbot is a chat, not a search box.)

## Options (20-question test set)
| mode   | hit@4 | MRR  | plain | reworded | exact code | follow-up | messy | avg ms | model calls |
|--------|-------|------|-------|----------|------------|-----------|-------|--------|-------------|
| vector | 90%   | 0.81 | 6/6   | 4/4      | 4/4        | 1/3       | 3/3   | 2154   | 0           |
| hybrid | 90%   | 0.70 | 5/6   | 4/4      | 4/4        | 2/3       | 3/3   | 2939   | 0           |
| rerank | 95%   | 0.83 | 6/6   | 4/4      | 4/4        | 2/3       | 3/3   | 6817   | 1           |
| full   | 100%  | 0.77 | 6/6   | 4/4      | 4/4        | 3/3       | 3/3   | 11699  | 2           |

## Decision
RAG_MODE=full: it is the only mode that finds the right chunk for all 20 questions, including all 3 follow-ups, and it meets the time limit.
Rewriting is what fixed the follow-ups ("And for P3?" and "How do I fix that if I'm not in the office?"), and follow-ups are normal in a chat.

## Consequences
- 2 model calls per question (one to rewrite, one to rerank), plus the answer call.
- About 11.7 s per question to retrieve, against 2.2 s for vector (timings vary from run to run).
- MRR is lower than rerank (0.77 against 0.83): the right chunk is found, but sometimes lower in the top 4.
- Only 20 questions: one question is 5 points, so rerank (95%) and full (100%) differ by a single follow-up.
- The documents disagree in places (the Markdown and PDF versions give different password expiry, lockout time and service desk hours). Search cannot fix that; the documents need fixing.

## Review when
The documents change, the model or embedding model changes, retrieval takes over 15 s, or the test set grows and the 95% / 100% gap changes.

### CLAUDE.md rule

> Retrieval changes are measured: any change to retrieval (chunking, search mode, reranking, rewriting or the number of chunks) must be measured with `scripts/compare_modes.py` before and after, and the numbers recorded.
