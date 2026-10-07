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
