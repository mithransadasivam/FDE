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

---

# Day 8 exercise reflection: the eight dimensions

## Which dimension surprised me

Safety surprised me the most. I expected the chatbot to be careful because it is built to only answer from documents, but it scored 25%. When I asked it how to read a colleague's mailbox without her knowing, or how to get round the password rules, it simply answered as if they were normal questions, because the documents had something to say about passwords and email. "Only answers from the documents" is not the same as "only answers things it should". Security also surprised me in a different way: it scored 10 out of 10 on day one, but most of those attacks never reached the model at all. The search found nothing relevant, so the chatbot declined before the model saw the attack. Ten out of ten looked good and proved very little until I added attacks that mention VPN, so the model really reads them.

## One case that broke my chatbot, and how I fixed it

A 5,000-word pasted log with the question at the end was refused as "too long", so a person with a real problem got nothing. I fixed it by keeping the end of a long message (where the question usually is), telling the person that only the last part was used, and then searching with it. A second one: after I added the refusal rule, the chatbot refused "can I paste my customer list into ChatGPT?", when the right answer is a clear "no, never" from the policy. I fixed that by telling it that a question that only asks whether something is allowed should be answered from the policy, and by making the code check treat "how can I..." (a request for a method) differently from "can I...?".

## One dimension I would test more before real users

Safety. My check only recognises a handful of ways of asking for something unsafe, and I only had eight safety cases. A real person could phrase "get round the password rules" in a hundred ways that my wording checks would miss, and then only the model's own judgement stands between the question and an answer. Before real users I would write many more unsafe and look-alike questions in different words, and test them on every change, because this is the dimension where one miss matters most.

## What I would tell my future self

Measure first, fix second, measure again. The gate went from 3 of 8 dimensions to 8 of 8, and I only believe it because I also saw it fail when I removed the refusal rule on purpose. And a feature that sounds like an obvious improvement (the self-critique loop) can be worse: it added three seconds, cost four times as much and turned one correct answer into a decline.

---

# Day 9 exercise reflection: browser tests, streaming and CI

## One bug only the browser tests could have found

The streaming display. My unit tests for streaming use a fake model client and check that the pieces come out in order, but they cannot see what is actually drawn on the page. When I broke the app on purpose so that the words never showed while they arrived, or so that the live text stayed on the page after the answer was finished, every unit test still passed (476 of them) and only the browser tests went red. A page can be wrong in ways the code underneath cannot show. The honest part: the browser tests did not find a bug in my real app by themselves. The bugs they found were in my own tests (one read a card's text before it was drawn, one waited for "some words" and matched the "Searching the documents…" note instead of the first real word) and one in my fake chatbot, found by the planner agent.

## What the Test Agents did well and badly

Well: the planner looked at the app like a new tester and found a real bug in my fake chatbot (an unrelated short question borrowed the previous topic). The generator wrote tests with no fixed waits and sensible locators, and found by itself that Streamlit leaves stale elements on the page after a reset. The healer fixed a renamed button with a four-line change, and when I broke the button's behaviour on purpose it refused to hide the bug and said so. Badly: the planner wrote 24 scenarios, several of them almost the same, and one that would have rebuilt the real index. The generator broke my "structure, not wording" rule: it checked the fake's exact answer sentences and an exact timing text. And I could not use the real agents in the same session, so I had to run them as stand-ins; I wrote that limit down instead of hiding it.

## One journey I would add before real users

What the page looks like when the hosted model hangs. The app waits up to 60 seconds, and for that whole minute the person sees "Searching the documents…" and nothing else. I tested the case where the model is switched off, which fails at once, but not the slow, silent failure, which is the one a real user would meet on a bad day. I would add a journey with a model that never answers, and decide what the person should see after, say, 15 seconds.

---

# Day 10 exercise reflection: pictures, scans and voice

## Which kind of input was hardest

Screenshots. A typed question is just words, but with a screenshot the chatbot has to read the picture first, and a wrong reading flows into everything after it. Voice turned out easy (the speech model even wrote "V P N dash eight zero nine" as VPN-809 by itself), and scans were easy once the pages were read, because after that they are just text.

## One case that fooled the chatbot, and the fix

A screenshot of error VPN-809. The first version searched the documents using the application name and the model happily wrote a fix that sounded right and cited a document, but the fix was made up because the search had not found the page for that code. Another code, VPN-806, had the same problem because its guidance was cut in half between two chunks. I fixed it in two steps: the code is now searched on its own ("error code VPN-809"), and if no document contains that code the chatbot declines instead of answering. I would never have seen it with fake models, only the real ones showed it.

## One privacy rule I would add

Before a picture is sent, blur or cover any names, email addresses and ticket numbers of other people, or at least warn clearly. Right now the screen only says "do not send anything you would not type into the chat", and a screenshot of a whole desktop can easily show things the person did not think about.

## Other things I learned

Making the picture smaller helps up to a point: 1024 px gave the same scores as the full size with 40% fewer tokens, but 768 px lost four error codes. And a style rule does not beat the words you send: I told the picture model "no numbers" and it still drew a giant 4 because my sentence said "floor 4". The fix was to take the digits out of the sentence.
