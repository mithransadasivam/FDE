# Journey map: one proof-of-address check

*One clean personal proof-of-address document (utility bill, bank statement or council tax bill). "Today" comes from the Day 1 interview notes and findings. "With UC1" comes from the design in ADR-001 (Option B: Textract OCR, then Claude Haiku on Bedrock, both in AWS London; a rules check; a review screen). Where I split a total into steps, the split is my estimate, and I say so.*

**Where the minutes come from**

- **T** = Tom's own figure: "A personal document is about six minutes if it's clean" (F06, interview 03:25). The data check agrees: 6.4 minutes on average for personal documents (`docs/DATA_CHECK.md`, claim 4).
- **S** = my split of Tom's 6 minutes across the steps. Tom gave one total, not a minute per step, so each split is an estimate to be measured. The step order and the pain points do come from what Tom said (interview 02:45 and 04:40).
- **E** = estimate for UC1. Nothing has been built or timed yet, so every "with UC1" minute is a guess to measure in the proof of concept.

| # | Step | Today: who does what | Minutes today | Pain today | With UC1: who does what | Minutes with UC1 (estimate to measure) |
|---|---|---|---|---|---|---|
| 1 | Document arrives | The applicant uploads it in the app or at a branch. It joins the queue (4,200 waiting, F02) until an analyst picks it up. | 0 (S): the wait is queue time, not analyst work | Documents wait days; the backlog grows (F01, F02) | The check service reads the case from CaseFlow (read-only), runs OCR and the model, and has the fields ready before an analyst opens it. No analyst work. | 0 (E). The queue wait is not removed by UC1 alone. |
| 2 | Open the case | Tom opens the case in CaseFlow on the left screen and the document in the viewer on the right. | 0.5 (S) | Two screens, constant switching (F05) | Tom opens one review screen: the page on one side, the extracted fields beside it. | 0.3 (E) |
| 3 | Read the document | Tom reads the whole document to find the name, address and date, and any part that is wrong. | 2.0 (S) | Reads every word to find one doubtful part (F12) | The model has filled in four fields, each with a confidence. Fields below the confidence limit are boxed on the page. Tom looks at the boxed ones first (F08, F09, F12). | 0.8 (E) |
| 4 | Check against the application | Tom checks name, address and date against the application form, by eye. About 29% of applications get an "ask applicant" (DATA_CHECK claim 3), often for blur or a document older than 3 months. | 1.5 (S) | Easy to miss an old date or a name mismatch; mistakes cause "ask applicant" rework (F07) | The rules check (date within 3 months, name, address) runs automatically and shows pass or doubt with the evidence. Tom confirms or overrules each one. | 0.8 (E) |
| 5 | Record in CaseFlow | Tom copy-types the key fields into CaseFlow, because it cannot read documents. The same address can be typed four times in one case (F05). | 1.5 (S) | Copy-typing and typing errors (F05) | Tom still types into CaseFlow, because its API is read-only for us and a change took 8 weeks last time (F17, F20). The review screen gives a copy button per field. **Nothing writes to CaseFlow.** | 0.7 (E) |
| 6 | Decide | Tom approves, asks the applicant, or escalates. He is accountable (F10). | 0.5 (S) | Evidence is scattered, so the audit trail is thin (F11) | Tom decides on the review screen, and the decision is logged with the evidence he saw (F10, F11). | 0.5 (E) |

**Total minutes per document:** today **6.0** (total from Tom, split by me) · with UC1 **3.1** (all estimates to measure) · source of each estimate: see the key above.

Check of the sums: today 0 + 0.5 + 2.0 + 1.5 + 1.5 + 0.5 = 6.0; with UC1 0 + 0.3 + 0.8 + 0.8 + 0.7 + 0.5 = 3.1. That is about 2.9 minutes saved per clean document. The 3-minute saving used in the cost numbers (`scripts/design_numbers.py`) is close to this, but it is also an estimate.

**What I am not claiming.** I have not seen Tom at work on a stopwatch. The split across steps is a guess, and a company document (20 minutes or more, F06) will look very different. The 2024 OCR pilot failed because it never said how sure it was (F08). If the confidence UC1 shows is not trusted, step 3 will not fall to 0.8 minutes, so step 3 is the first thing to measure.

## The moment that matters most

**Step 3, reading the document.** It is the biggest block today (2.0 of 6.0 minutes by my split) and the one the 2024 pilot got wrong. Today Tom reads every word to find the one doubtful part (F12). With UC1 he sees the fields boxed on the page, each with a confidence, so he knows where to look first and where each answer came from (F08, F09). If this step does not work, the analysts will not trust the tool, whatever happens in the other steps.

## What still needs a person

The analyst decides in every row. UC1 prepares, highlights and suggests; it never approves, asks or escalates (Helen, F10: "That is not negotiable").

- **Step 1:** UC1 only prepares the fields. No document is approved on arrival.
- **Step 2:** the analyst chooses what to open and how to read the case.
- **Step 3:** the analyst judges the doubtful fields. A model can be wrong with high confidence, so a boxed field means "look here", and an unboxed field does not mean "correct".
- **Step 4:** the rules pre-check is a suggestion. The analyst confirms or overrules, because a pass on date and name does not mean the document is genuine.
- **Step 5:** the analyst types into CaseFlow, because it is read-only for us (F17). This is a limit, and it is also safe: only people write to CaseFlow.
- **Step 6:** the analyst makes and owns the decision (F10), and the audit log shows who decided what, when, and on what evidence (F11).
