# Reflection

## Which phase was hardest to describe to the agent?

Phase 8 was the hardest for me to explain to Claude. The brief asked me to use my Day 2 security reviewer, but Claude could not find it, and I could not find it myself either. This meant I had to ask Claude to create a new one. It was not a huge issue, just a minor one.

## One request I had to rewrite, and why

While testing the app, localhost port 8501 kept showing the chatbot we built in class instead of the new one. I had forgotten to ask Claude to quit that earlier session. Once I asked Claude to close it, the new chatbot started correctly.

## One thing I would do differently

I would use more than 10 test questions. For an IT chatbot like this, a better version needs many more test questions, because there are so many different IT problems that people face every day, and the chatbot should be prepared for them. This also means I would add more documents, including more PDFs, so that they cover these types of questions.

---

# Part 2 reflection: measuring retrieval

## Which technique helped the most, and why

Reranking helped the most. It was the only mode to get all 20 questions right (100%), and it gave the best MRR (0.94, against 0.79 for plain vector search). The reason is that plain search often found the right chunk but put it second or third. Reranking asks the model to look at the top 10 candidates and put the best one first, so the right answer ends up near the top more often. The problem is time. It adds a model call to every question, so a whole answer took about 4 seconds, which is over my 3 second target. Because of that I did not choose it.

## One technique that did not help

Query rewriting (the "full" mode) did not help. It was supposed to fix follow-up questions like "And on a Mac?", and it does work on that one: it turns it into "How do I install the VPN client on Mac", which finds the right chunk. But hybrid search and reranking had already fixed most of the follow-ups, so rewriting added almost nothing. It got 95% and was slower than reranking at about 5.6 seconds, with three model calls per answer. Hybrid search was also a disappointment. It had the lower hit rate (90%, against 95% for vector) because chatty words in the question matched the wrong documents. All my exact-code questions already worked with plain vector search, so there was nothing for the keyword search to improve.

## One question that still fails, and why

With the mode I chose (vector), the question "What if it still fails after that?" still fails. It is a follow-up to a VPN question, but on its own the words "still fails" say nothing about VPNs, so the search returned error-code and Wi-Fi chunks and the right VPN chunk came 5th, outside the top 4. Rewriting the question with the previous one fixes it, but I decided the extra time was not worth fixing one question in 20. If a lot of people ask follow-up questions, I would look at this again.

## What I decided

I kept plain vector search. It already met both targets (95% hit rate, about 2 seconds per answer), and my rule was to keep the simplest mode that meets the target. All four modes still answered and declined correctly in the 10-question test from Part 1, so a better search did not break that. The full reasoning is in RAG_DECISION.md.
