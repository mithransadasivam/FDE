# Discovery session transcript: Kestrelmoor Bank, KYC Operations

*Reference recording of a discovery session, condensed to its key ten minutes. Fictional people and numbers. Speakers: FDE (the forward deployed engineer), Deborah Okafor (Head of KYC Operations), Tom Reyes (Senior KYC Analyst), Helen Achebe (MLRO).*

---

**[00:00] FDE:** Thanks for making the time. Before we talk about AI at all, I'd like to understand how onboarding works today and where it hurts. Deborah, could you start with the problem in your own words?

**[00:20] Deborah:** The problem is simple: we promise customers a decision in three working days and we are nowhere near it. Our median is seven working days, and the worst cases go past twelve. Right now we have 4,200 documents waiting for an analyst.

**[00:45] FDE:** How long has the backlog been building?

**[00:50] Deborah:** Since about March. Volumes went up after the new app launched, and my headcount didn't.

**[01:05] FDE:** What volume are you handling each week?

**[01:10] Deborah:** About 1,900 applications a week, and on average 2.4 documents per application. But that average hides the real story.

**[01:25] FDE:** What does it hide?

**[01:30] Deborah:** Business accounts. They are only about 15 percent of applications, but they take about 40 percent of my analysts' time. A sole trader is easy. A limited company means a certificate of incorporation, the directors, the people with significant control, and checking all of it against Companies House.

**[02:05] FDE:** Is the volume steady through the year?

**[02:10] Deborah:** No. January and September are our peaks: volumes roughly double. September is students opening accounts, January is people switching banks in the new year. If we don't fix this before January, it gets much worse.

**[02:35] FDE:** Tom, could you walk me through what you actually do with one application, from the moment you open it?

**[02:45] Tom:** Sure. I work on two screens. CaseFlow, our case management system, is on the left, and the document viewer is on the right. I open the case, open the first document, and check it against the application: name, date of birth, address. Then I copy-type the key fields into CaseFlow, because CaseFlow can't read the documents itself.

**[03:20] FDE:** How long does one document take?

**[03:25] Tom:** A personal document is about six minutes if it's clean. A company document can be twenty minutes or more, because you're cross-checking directors and owners.

**[03:40] FDE:** You said "if it's clean". What happens when it isn't?

**[03:45] Tom:** Then we ask the applicant for something else. About 31 percent of applications get at least one "ask applicant". The usual reasons are a proof of address older than three months, a blurred photo of a passport, or a name that doesn't match, like a maiden name on a utility bill.

**[04:15] FDE:** And when the new document comes back?

**[04:20] Tom:** It goes back into the queue, usually to a different analyst, who starts the case again from the beginning. That rework is a big part of the backlog.

**[04:35] FDE:** What's the most frustrating part of the job for you?

**[04:40] Tom:** Honestly, the copy-typing. I've typed the same address four times in one case. And switching between the two screens all day.

**[04:55] FDE:** Has the bank tried to automate any of this before?

**[05:00] Deborah:** We did, in 2024. We ran a pilot with an OCR vendor that read the documents and filled the fields in.

**[05:10] FDE:** What happened?

**[05:15] Tom:** We stopped using it after four months. The problem was that it never told you how sure it was. Every field looked equally confident, so we ended up rechecking everything it did, and that was slower than doing it ourselves.

**[05:35] Deborah:** That pilot has left scars. My analysts will not trust a tool that can't show them where an answer came from.

**[05:45] FDE:** That's really useful. What data do you keep about past reviews?

**[05:50] Tom:** CaseFlow keeps everything. We have about 18 months of history: roughly 61,000 document reviews, with the analyst's decision and a reason code for every "ask applicant" or escalation.

**[06:10] FDE:** Can we get an export of that?

**[06:15] Deborah:** I think so, but it contains customer data, so Helen will need to agree how.

**[06:20] FDE:** How do systems connect today? Can anything read from or write to CaseFlow?

**[06:25] Tom:** CaseFlow has an API, but it's read-only for us. Writing anything back needs a change from the vendor, and the last change took eight weeks.

**[06:40] FDE:** Helen, thanks for joining. What would worry you about using AI in this process?

**[06:50] Helen:** Two things. First, a person must make every KYC decision. A tool can prepare, highlight and suggest, but an analyst decides and is accountable. That is not negotiable.

**[07:10] FDE:** And the second?

**[07:15] Helen:** Any change to our KYC controls needs my sign-off, and anything that uses a model needs an independent model validation before it goes into production. In practice that takes about three weeks, so plan for it.

**[07:35] FDE:** Are there rules about where the data can be processed?

**[07:40] Helen:** Customer documents must not leave the UK. Our cloud is AWS in the London region, and nothing goes to public AI chat tools. Staff are already blocked from those.

**[07:55] FDE:** Understood. Deborah, how will Martin judge whether this engagement worked?

**[08:00] Deborah:** Martin looks at two numbers. Cost per application, which is about £11.40 today, and abandonment. About 22 percent of applicants give up when onboarding takes more than five days, and many of them go to a competitor.

**[08:25] FDE:** And how will you judge it?

**[08:30] Deborah:** If we're back inside three working days for most customers before the January peak, I'll be happy. And if my analysts actually want to use the tool.

**[08:45] FDE:** If you could change one thing tomorrow, what would it be?

**[08:50] Tom:** Stop the copy-typing, and show me straight away which part of a document is the problem, so I don't have to read the whole thing to find it.

**[09:05] Deborah:** For me it's the business accounts. That's where the hours go.

**[09:15] FDE:** One last question: is there anything we haven't asked that we should have?

**[09:20] Helen:** Ask about the audit trail. Whatever the tool does, we must be able to show a regulator who decided what, when, and on what evidence.

**[09:35] FDE:** Thank you all. I'll send a written summary of what we heard by tomorrow, with the open questions, so you can correct anything we got wrong.
