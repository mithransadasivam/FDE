# Classifying my capstone: Northwind IT Help Desk Chatbot

**Category: limited risk, resting on Article 50 of the EU AI Act (transparency).** From 2 August 2026, so it already applies today. This is a first sorting for the inventory, not legal advice. If anything below turns out to be borderline, it goes to compliance.

The chatbot answers staff questions about IT policy (VPN, passwords, laptops, support targets) from seven policy documents, cites where each fact came from, and declines when the documents don't cover the question. With its tools it can also look up help desk tickets and assets, and a person has to approve any change to a ticket. I answered the questionnaire by reading the code, then checked each answer myself.

## The answers, one at a time

| Question | Answer | Why |
|---|---|---|
| Is it a banned practice (Article 5)? | No | It only answers from company IT documents. It doesn't manipulate anyone, score people, read emotions or touch biometrics, so none of the Article 5 practices fit. |
| Is it a safety component of a regulated product (Annex I)? | No | It is an internal help desk tool. It isn't part of a machine, vehicle, medical device or any other regulated product. |
| Does it sit in an Annex III area? | None | It answers IT questions. It doesn't decide anything about hiring, pay, promotion, education, credit or benefits, so none of the eight areas applies. |
| Is it only a narrow or preparatory task (Article 6(3))? | No, but it doesn't matter | That exception only helps a system that is already in an Annex III area. This one isn't. |
| Does it profile people? | No | It answers the question that was asked. It builds no profile of the user and doesn't store questions, only request metadata (time, route, cost). |
| Does it talk to people or generate content? | Yes | Staff chat with it directly and it writes answers in its own words. This is what puts it in the limited category. |

Going down the questionnaire in order, the first four answers rule out prohibited and high risk. The last one is a yes, so the category is limited (Article 50).

## What it means for us

- **Obligation:** tell people they are talking to an AI system (Article 50(1)), and mark generated content as AI-generated where Article 50 asks for it.
- **Date:** 2 August 2026. That has already passed.
- **Where we stand:** we are not compliant yet. The chat page says "Answers only from your team's documents · every fact cited" and calls itself an "IT Help Desk Assistant", but nowhere says it is an AI. I checked `app/ui.py` and the static chat page. This is risk C01 in the register, open, with a review date of 15 November 2026. The fix is small: one visible line on the chat page and in the `/ask` response.
- **Every AI system:** staff who use it need AI literacy (Article 4), whatever its category.
- **Not required, but sensible:** the model card and the risk register, which I kept anyway.

## The one change that would move it up

**Letting the chatbot make or shape decisions about people.** The simplest example is a new feature that decides who gets a laptop upgrade, or that ranks staff by how many tickets they raise to feed a performance review. That would bring it under Annex III point 4 (employment and workers management), which is high risk, with a risk management system, logging, human oversight and a conformity assessment, due from 2 December 2027. Anything that profiles individual staff also removes the Article 6(3) way out. So before building a feature like that, I would stop and ask compliance first.

A second, smaller trigger: if it ever read the faces or voices of staff to guess their mood (the voice-to-ticket feature from Day 10 is close enough to watch), that would be a banned practice at work under Article 5(1)(f).
