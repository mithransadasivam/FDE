# RAG decision: which retrieval mode to keep

## What I was deciding
How the chatbot should find the right chunks of text before it answers. I tested four ways: plain vector search, hybrid (vector plus keyword search), reranking (the model re-orders the best 10 candidates), and full (rewrite the question, then hybrid, then rerank).

## My target (set before I measured anything)
- Hit rate of at least 90%: the right chunk is in the top 4 for at least 18 of my 20 test questions.
- A whole answer (search plus the model writing the reply) in 3 seconds or less.
- If more than one mode meets the target, I keep the simplest one.

## What I measured
20 test questions (6 plain, 4 reworded, 4 with exact codes, 3 follow-ups, 3 messy), top 4 chunks, 23 documents and 62 chunks. Each mode also ran the 10-question answer-or-decline test from Part 1.

| Mode | Hit rate | MRR | Search time | Model calls per answer | Answer or decline | Whole answer | Meets target |
|---|---|---|---|---|---|---|---|
| vector | 95% (19/20) | 0.79 | 123 ms | 1 | 10/10 | 1.97 s | yes |
| hybrid | 90% (18/20) | 0.87 | 111 ms | 1 | 10/10 | 2.11 s | yes |
| rerank | 100% (20/20) | 0.94 | 2272 ms | 2 | 10/10 | 4.01 s | no |
| full | 95% (19/20) | 0.91 | 3411 ms | 3 | 10/10 | 5.63 s | no |

## My decision: vector
- Plain vector search already meets both parts of my target, so I don't need anything more complicated.
- Hybrid also meets the target, but it found fewer right chunks (90% against 95%). It lost two questions that vector got right.
- Rerank was the most accurate, but a whole answer takes about 4 seconds, which is over my 3 second limit.
- Full was the slowest (about 5.6 seconds) and no better than rerank, so it was not worth the extra calls.
- None of the modes broke the Part 1 behaviour. All of them answered the 7 answerable questions and declined the 3 unanswerable ones. With vector, the saved run is 10/10.

## What it costs
Vector search needs no extra model calls, takes about 0.1 seconds to search, and a whole answer is about 2 seconds. Rerank would add one model call and about 2 seconds to every question.

## Limits I know about
- 20 questions is not many. One question is worth 5 points of hit rate, so the gap between vector (95%) and hybrid (90%) is a single question.
- Hybrid depends on how many candidates it uses. A quick check with 3 or 5 candidates gave 20/20, so it may be worth another look.
- Times change a little from run to run, and they include how fast the model happens to reply.
- My Northwind documents and the class PDFs disagree on 5 facts (password expiry, lockout time, service desk hours, lost equipment deadline, guest Wi-Fi). The bot can quote either one. I have not fixed this.
- One follow-up question still fails with vector: "What if it still fails after that?"

## When I will measure again
- After any change to the documents, chunk size, embedding model, number of chunks, or minimum score.
- Before adding any new retrieval step. I run `python -m scripts.compare_modes` before and after and compare the numbers.
- If people start asking a lot of follow-up questions, because rerank and hybrid handled those better than vector.
