# Part 2 working notes

Running notes for Part 2 (retrieval measurement). The final decision goes in `RAG_DECISION.md` (Phase 14).

**Target, set before any numbers existed:** hit rate at least 90% **and** an answer within 3 seconds.
**k = 4** (the number of chunks the chatbot puts in its prompt). Scoring depth: top 10 chunks, so MRR can still credit a chunk found below rank 4.
**Test set:** `data/retrieval_test_set.csv`, 20 questions (6 plain, 4 reworded, 4 exact code, 3 follow-up, 3 messy). Evidence check: 20 of 20 found.
**Knowledge base:** 23 documents, 62 chunks (17 Northwind markdown + 5 Day 6 policy PDFs + 1 Day 7 error-code PDF).

## Phase 10: baseline (mode "vector")

| Measure | Result |
|---|---|
| Hit rate @4 | **19 / 20 = 95%** |
| MRR | **0.79** |
| plain | 6 / 6 |
| reworded | 4 / 4 |
| exact code | 4 / 4 |
| follow-up | 2 / 3 |
| messy | 3 / 3 |
| Average retrieval time | 120 ms per question (0 model calls) |

**The one miss:** "What if it still fails after that?" (follow-up, previous question: "My VPN keeps disconnecting. What can I try?"). Searching with only the follow-up text, the right chunk (`vpn_troubleshooting.md`) came 5th; the top results were about error codes and Wi-Fi. Without the previous question the words "still fails" carry no VPN meaning. This is exactly what query rewriting (Phase 13) should fix.

**Which kinds fail most:** only follow-ups. But MRR (0.79) is lower than the hit rate: seven right chunks sit at rank 2 or 3 (e.g. reworded "What laptop does a new starter get?" at rank 3, messy questions at rank 3), so reranking has room to improve the *order*. Exact-code questions already all score rank 1, so hybrid search has little room to win on this test set.

**Already above the hit-rate target.** The 90% target is met by plain vector search (95%). Under the rule "keep the simplest mode that meets the target", any extra mode has to earn its place on something other than the hit rate (MRR, the follow-up miss) without breaking the time target.

**Measurement fix found during this phase:** the first baseline run took 2,172 ms per question, almost exactly the same for every question. Cause: the Ollama address used `localhost`, which on Windows tries IPv6 first and waits about 2 seconds before using IPv4. Direct test: `localhost` 2.08 s, `127.0.0.1` 0.07 s for one embedding call. The address was changed to `127.0.0.1` and the baseline re-run: same accuracy (95%, MRR 0.79), 120 ms per question. This also removes about 2 seconds from every answer in Part 1. A test now guards the address.

## Phase 11: hybrid search (mode "hybrid", 10 candidates from each search)

Keyword search (BM25, `rank-bm25`) over every stored chunk, a tokenizer that keeps codes like `VPN-809`, `5.2` and `reset.northwind.example` whole and drops very common words, and reciprocal rank fusion (constant 60) of the keyword list and the meaning-based list. Each chunk keeps its cosine similarity (also keyword-only chunks, computed from the stored embedding), so the minimum-score guard still works.

| Measure | vector (baseline) | hybrid (10 candidates) |
|---|---|---|
| Hit rate @4 | 19 / 20 = 95% | **18 / 20 = 90%** |
| MRR | 0.79 | **0.87** |
| plain | 6 / 6 | 6 / 6 |
| reworded | 4 / 4 | 3 / 4 |
| exact code | 4 / 4 | 4 / 4 |
| follow-up | 2 / 3 | 3 / 3 |
| messy | 3 / 3 | 2 / 3 |
| Retrieval time | 120 ms | 133 ms (0 model calls) |

**Did exact-code questions improve?** No. All four were already at rank 1 with vector search, so there was nothing to win. This matches the baseline prediction.

**Did anything get worse?** Yes. Six questions moved up, three moved down, and two of those fell out of the top 4:
- "What laptop does a new starter get?" (reworded): rank 3 to 5. Keyword matches on "laptop" and "new" pulled in the equipment policy and an error-code chunk.
- "morning! so i'm leaving the company on friday, when do my logins get switched off?" (messy): rank 1 to 5. The right chunk was the best meaning-based match (0.66) but the chatty words ("company", "friday", "off", "morning") matched unrelated chunks by keyword, and chunks found by both searches rank above a chunk found by one.
- "I forgot my password..." (reworded): rank 1 to 2 (still a hit).

**Why it helped the follow-ups:** the one baseline miss ("What if it still fails after that?", rank 5) is now rank 2, and "And on a Mac?" and the laptop-notice follow-up moved from rank 2 to rank 1. Words like "fails" and "replaced" match the right document by keyword even without the previous question.

**Sensitivity to the number of candidates** (checked afterwards, on the same 20 questions, so treat it as a hint and not as proof):

| Candidates | Hit @4 | MRR |
|---|---|---|
| 3 | 20 / 20 | 0.90 |
| 5 | 20 / 20 | 0.89 |
| **10 (chosen)** | 18 / 20 | 0.87 |
| 20 | 18 / 20 | 0.86 |

With fewer keyword candidates there is less keyword noise, so the meaning-based ranking stays in charge. The setting stays at the chosen 10 until the project owner decides otherwise; changing it after looking at these results risks fitting the 20 questions.

## Phase 12: reranking (mode "rerank": hybrid candidates, then the model judges up to 10 in one call)

One model call per question sends the question and the candidates (wrapped in `<candidate>` tags, escaped, treated as data) and asks for `{"scores": [...]}` from 0 to 10. The best k are kept; ties keep their order; an unreadable reply or an unreachable model keeps the original order. Each chunk keeps its similarity score, so the minimum-score guard still works. Decision made by the project owner: the reranker judges **10** candidates.

| Measure | vector | hybrid | rerank |
|---|---|---|---|
| Hit rate @4 | 19 / 20 = 95% | 18 / 20 = 90% | **20 / 20 = 100%** |
| MRR | 0.79 | 0.87 | **0.94** |
| plain | 6 / 6 | 6 / 6 | 6 / 6 |
| reworded | 4 / 4 | 3 / 4 | 4 / 4 |
| exact code | 4 / 4 | 4 / 4 | 4 / 4 |
| follow-up | 2 / 3 | 3 / 3 | 3 / 3 |
| messy | 3 / 3 | 2 / 3 | 3 / 3 |
| Retrieval time per question | 120 ms | 133 ms | **about 2.2-2.3 s** |
| Model calls per question | 0 | 0 | 1 |

**Did the MRR rise more than the hit rate?** Yes. Against vector, the hit rate rose 5 points (95% to 100%) but the MRR rose 0.15 (0.79 to 0.94). Reranking mostly improves the *order*: 18 of 20 right chunks are now at rank 1 (vector: 13).

**What it fixed:** the two questions hybrid broke are back in the top 4 ("What laptop does a new starter get?" rank 2, the leaver question rank 1), and it keeps hybrid's fix for the follow-up miss ("What if it still fails after that?" rank 3).

**Stable and reliable?** Run twice with the same settings: both gave 20/20 and MRR 0.94. In the second run (when fallbacks started being counted) **1 of 20 replies could not be used** and the original order was kept ("What is VPN-815?", which still ranked first). The fallback worked as designed; about 1 in 20 unusable replies is a cost to remember.

**Cost:** one model call per question, about 1.5 to 5 seconds (typically 2). That is about 18 times slower than vector in retrieval alone (2.2 s vs 0.12 s). Because the chatbot then makes a second model call to write the answer, a full answer through rerank mode will take longer than the retrieval time shown here.

**Open question for Phase 14: how the 3-second target is measured.** The target was written as "an answer within 3 seconds". If that means the whole answer (retrieval plus the model writing the reply, about 2 s), rerank will miss it even though its retrieval alone (2.2 s) is under 3 s. Phase 14 will measure the full answer time with the chosen mode and say which reading is used.

## Phase 13: query rewriting (mode "full": rewrite, then hybrid, then rerank = 2 model calls)

The model turns what the user typed into one short standalone search query, using **only the previous user question** from the real chat history (decision by the project owner), keeping codes and numbers as typed. A reply that is empty, longer than 200 characters or on more than one line, or an unreachable model, falls back to the original question. The chat shows "Searched for: ..." under each answer. Only the full mode rewrites; the other modes search for the question as typed.

| Measure | vector | hybrid | rerank | full |
|---|---|---|---|---|
| Hit rate @4 | 19 / 20 = 95% | 18 / 20 = 90% | **20 / 20 = 100%** | 19 / 20 = 95% |
| MRR | 0.79 | 0.87 | **0.94** | 0.91 |
| plain | 6 / 6 | 6 / 6 | 6 / 6 | 6 / 6 |
| reworded | 4 / 4 | 3 / 4 | 4 / 4 | 4 / 4 |
| exact code | 4 / 4 | 4 / 4 | 4 / 4 | 4 / 4 |
| follow-up | 2 / 3 | 3 / 3 | 3 / 3 | 2 / 3 |
| messy | 3 / 3 | 2 / 3 | 3 / 3 | 3 / 3 |
| Retrieval time | 120 ms | 133 ms | ~2.2 s | **~3.6 s** |
| Model calls | 0 | 0 | 1 | 2 |

**Did the follow-up and messy questions improve?** Not beyond what earlier modes already did.
- Follow-ups: the rewrite did what it should for two of them. "And on a Mac?" became "How do I install the VPN client on Mac" and "And how much notice do I get before it is replaced?" became "laptop replacement notice period"; both rank 1. But hybrid search had already fixed those two (rank 1 without rewriting).
- The remaining follow-up, "What if it still fails after that?", got worse: the rewrite was "VPN keeps disconnecting troubleshooting steps", which resolved the reference but lost the meaning "it still fails, so what next". The right chunk (the "Still stuck: open a ticket and attach the log file" section) fell from rank 3 (rerank) to rank 7.
- Messy questions: all 3 hit rank 1 or 2, the same as rerank alone. The rewrites were sensible ("lost phone recovery procedure", "offboarding login deactivation timeline", "paste customer list into ChatGPT"), but those questions were already found without rewriting.
- Exact codes: "A visitor got WIFI-117..." slipped from rank 1 to 2 (rewrite: "WIFI-117 guest network error code meaning").

**Cost:** two model calls per question, about 3.6 s retrieval on average (vs 2.2 s for rerank). Through the real app (full mode, retrieval plus the answer call) the two answers in the follow-up check took 6.7 s and 4.9 s.

**End-to-end follow-up check** (real app code, real Ollama and model, full mode): after "How do I install the VPN client on Windows?" (searched for "install VPN client Windows"), the follow-up "And on a Mac?" was searched for as "How to install VPN client on Mac" and answered with the Mac steps, citing `vpn_setup_guide.md` page 1.

**Caveat:** one run, one rewrite per question. Rewrites vary a little from run to run (temperature 0.1), and the test set has 3 follow-ups and 3 messy questions, so a difference of one question is within noise.

## Phase 14: comparison and decision

| Mode | Hit @4 | MRR | Retrieval | Calls per answer | Behaviour | Whole answer | Meets target |
|---|---|---|---|---|---|---|---|
| vector | 95% | 0.79 | 123 ms | 1 | 10/10 | 1.97 s | yes |
| hybrid | 90% | 0.87 | 111 ms | 1 | 10/10 | 2.11 s | yes |
| rerank | 100% | 0.94 | 2272 ms | 2 | 10/10 | 4.01 s | no |
| full | 95% | 0.91 | 3411 ms | 3 | 10/10 | 5.63 s | no |

Chosen: **vector** (the simplest mode that meets the target). Part 1 behaviour test with vector: run 3, 10/10, 7/7 answered, 3/3 declined, 2.13 s average. See `RAG_DECISION.md`.
