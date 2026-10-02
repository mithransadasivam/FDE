# Findings, Day 6: chatbot over 20 Ollama docs

## Documents
20 public Ollama documentation files (MIT licensed, from github.com/ollama/ollama `docs/`), saved in `data/my_docs/`: 18 top-level pages (api, cli, cloud, context-length, development, docker, examples, faq, gpu, import, index, linux, macos, modelfile, quickstart, template, troubleshooting, windows) plus `capabilities/embeddings` and `capabilities/structured-outputs`. 394 chunks in total. No file produced 0 chunks. Largest: ollama_api.md (135 chunks); smallest: ollama_examples.md (1 chunk).

## Results
| Run | RAG_MIN_SCORE | Behaviour correct (script's score) |
|---|---|---|
| Before | 0.50 | 7 of 10 |
| After | 0.60 | 7 of 10 (identical answers) |

Threshold kept: 0.50. Raising it changed nothing, because the four chunks retrieved for each of the three "not covered" questions and for Q6 all scored between 0.67 and 0.78 (the other questions were not scored one by one), so all four chunks passed 0.6 as well as 0.5. Top scores of the three "not covered" questions: Raspberry Pi 0.781, FreeBSD 0.767, cloud price 0.692. The answerable Q6 scored 0.765. No single threshold separates them.

The script's score understates the chatbot on declines. For Q6 and Q8 to Q10 the model said "I don't know: the documents don't cover that." and then added an explanation. `answer()` only counts an exact match with that sentence as declined, so these four are all marked `answer`. Reading the answers myself, 9 of 10 behaviours are right (only Q6 is wrong).

## Failures
- Wrong answer: none among the six answered questions (Q1 to Q5, Q7). Each matches its expected answer.
- Wrong citation: none found. For Q1 to Q5 and Q7, the cited numbers point to a source file whose text contains the fact (checked Q1, Q4 and Q7 against the file text).
- Answered when it should decline: Q8 (Raspberry Pi), Q9 (FreeBSD) and Q10 (cloud price) are marked MISS, but the model did decline in substance. This is a scorer exact-match issue, not a chatbot fault.
- Declined when it should answer: Q6 "How can I make Ollama reachable from other computers on my network?" The model declined. The answer is in ollama_faq.md ("Ollama binds 127.0.0.1 port 11434 by default. Change the bind address with the OLLAMA_HOST environment variable"), and retrieval returned three faq chunks. Q6 is also scored OK by mistake, for the same exact-match reason.

## Next
Fix Q6 on Day 7: the answer sits in the retrieved FAQ chunks but the model still declined, so look at chunking (a 500-character chunk may separate the heading from the answer; not yet checked) and at the decline check, which should treat "starts with the decline sentence" as declined.
