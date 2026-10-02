# Tuning record (Phase 7)

One setting changed: the minimum score (Guard 1). Everything else identical (chunk size 500, overlap 100, 4 chunks, temperature 0.1).

| Run | Minimum score | Behaviour correct | Answered when it should | Declined when it should | Avg time |
|---|---|---|---|---|---|
| 1 (baseline) | 0.55 | 10 / 10 | 7 / 7 | 3 / 3 | 3.86 s |
| 2 (stricter) | 0.65 | 9 / 10 | 6 / 7 | 3 / 3 | 3.68 s |

**Miss in run 2:** question 7, "I lost my phone on the train - who do I call?". Its best retrieval score was 0.61, below 0.65, so Guard 1 declined it without asking the model.

**Decision:** keep 0.55. The scores for covered questions go as low as 0.61 and the unrelated salary question scores 0.51, so any minimum between about 0.52 and 0.60 works on this test set; 0.55 sits in that gap.

**What the minimum score cannot do:** the near-miss questions (floor 3 printer 0.72, Linux laptops 0.71) score as high as real answers. They were declined by Guard 2 (the model's decline sentence), not by the score, in both runs.

**Manual check (run 1):** every answer and citation was read against the documents; all facts and cited pages were correct.
