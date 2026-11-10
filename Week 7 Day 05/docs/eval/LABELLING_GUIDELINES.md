# Labelling guidelines · v2

For anyone labelling UC1 proof-of-address extractions. Written so a second analyst who was not in the Day 4 session can label and agree with Tom.
v2 keeps everything from v1 (names and dates, as agreed with Tom in the two labelling rounds) and adds address and issuer, one real example per field, the hard cases and what to do when unsure.

## The rule

A value is **correct** when it is exactly what the document prints for that field, nothing missing and nothing added, and it is the right item on the page (the issue date, not the payment date; every person addressed, not just the first). Judge the value against the page, never against the application and never against what the rules would do with it.

## Field by field

| Field | Correct | Wrong | Example from the evaluation set |
|---|---|---|---|
| Full name | Everyone the document is addressed to, titles included, joined as printed (`Mr A Shah & Mrs P Shah`). Initials exactly as printed. | A joint bill with a name missing. A name with the title dropped or an initial expanded. | **L03 · D04-033** `Mr Arun Shah`: **wrong**, the bill is addressed to Mr Arun Shah & Mrs Priti Shah. **L02 · D03-008** `Mr J. A. Kowalski`: **correct**, initials as printed. |
| Address | The postal lines in the printed order, flat number and postcode included, joined with ", ". If the page prints `number street, Flat n`, that is the correct order even when the application says `Flat n, number street`. | A line, flat number or postcode missing, or the lines re-ordered to match the application. | **L11 · D04-041** `8 Brunswick Road, Flat 5, Gloucester, GL1 1JJ`: **correct** as printed (the application writes it `Flat 5, 8 Brunswick Road`). *No wrong address has appeared in the 100 cases so far; the wrong column is the rule, not an observed example.* |
| Statement date | The date beside an issue label: "Statement date", "Date of issue", "Bill date", "Issued". Written as printed. | A payment due date ("Payment due", "Due by", "Pay by"), a billing period or a transaction date, even when it is printed first. | **L01 · D04-031** `03 Oct 2026`: **wrong**, it is the payment due date. **L08 · D04-037** `01 Oct 2026`: **correct**, "Date of issue" on a council tax bill. |
| Issuer | The organisation's name as printed, legal suffix included (`LUMENVALE ENERGY LTD`, `Northmere Bank plc`), capitals as printed. The name only: stop before the service tagline (`Water & Sewerage`, `Electricity & Gas`). | Another organisation, a name that is not printed, or the name with the tagline run on. | **L10 · D04-036** `LUMENVALE ENERGY LTD`: **correct** as printed. **D04-043** the model's `Harrowgate Water & Sewerage` against the label `Harrowgate Water`: **wrong**, the tagline is not part of the name. |

## What a label is not

- **Not a decision.** D04-036's issuer is correct as printed even though the approved-issuer rule rejects `LUMENVALE ENERGY LTD`. That is a rules problem, not a label problem. Never bend a label to make a rule pass.
- **Not a measure of confidence.** Correct or wrong; "probably" is not a label (see "When you are not sure").
- **Not a view of the application.** Do not open the application form to decide a label. Whether the name or address matches the applicant is a separate check.
- **Not a check on the scan.** Label what the document says. If the OCR misread a digit (D03-009 prints 18 Sep, OCR read 16 Sep) the label stays the true value, and the miss is a failure of reading, which is a different fix.

## Hard cases, decided

| Case | The question | The decision, and who made it |
|---|---|---|
| D04-037 | Is "Date of issue" on a council tax bill the statement date? | Yes, statement date. Tom (label `01 Oct 2026` correct). |
| D04-031, D04-034, D04-038 | Two dates are printed and the payment date comes first: which is the statement date? | The date beside the issue label. The payment date is wrong. Tom. In round 1 (guidelines v0) the saved labels called D04-031 and D04-034 correct and Tom called them wrong; round 2 (v1) fixed both. |
| D04-033, D04-040, D04-046, D04-048 | A joint bill: is the first name alone enough? | No. Both names must be recorded. Tom ("Joint bill: both names must be recorded"). `Mr Tariq Aziz` (D04-040) was still a disagreement with Tom in round 2 (v1), so the rule is stated in full here. |
| D03-008 | Initials: expand or keep as printed? | As printed (`Mr J. A. Kowalski`). Tom. |
| D04-036, D04-049 | Issuer printed with a legal suffix or in capitals: same company, which form is the label? | Same company; the label is the name as printed, suffix included. Tom ("Same company: its legal name"). |
| D04-041, D04-045 | Address printed `number street, Flat n`: is that the same flat as `Flat n, number street`? | Same flat; the label keeps the printed order. Tom ("Same flat, written the other way round"). |
| D03-010, D04-043 | Issuer header reads `Harrowgate Water Water & Sewerage`: is the tagline part of the issuer? | No: `Harrowgate Water`. Tom's label; the extraction run copied the tagline in 4 of 50 real cases with extract_v2 and 6 with extract. Written down by me after the Day 4 homework runs, so Tom should confirm. |
| S-143 | A synthetic case is both a joint bill and an issuer variant (`Fenwick Gas & Power plc`, two names). Which slice? | It is labelled issuer_variant but the name label records both people (joint rule applies). Me, from the guidelines; Tom to confirm. |
| S-140, S-143 | A synthetic statement date after the application date (05 Nov 2026, 01 Dec 2026). Does that change the label? | No. The label is what the page prints; whether the date passes the three-month rule is a rules question. Me. |

## When you are not sure

Do not guess and do not pick the likelier value. Mark the item **unsure**, write one line saying what you could not decide, and leave it out of the scores until it is answered. Ask Tom, in the labelling thread, with the case id and a screenshot or the OCR words. Tom's answer becomes a new row in the hard-cases table above, with his name, so the next labeller does not have to ask again. If a synthetic label makes you hesitate, the guidelines are missing a line: add it, then fix or delete the case and record which in `evals/synthetic/LABEL_NOTES.md`.
