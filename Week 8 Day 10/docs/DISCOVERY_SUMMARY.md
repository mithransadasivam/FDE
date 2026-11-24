# Discovery summary: Kestrelmoor Bank, KYC onboarding

*Draft for client review, 02 November 2026.*

## Pain points

- **Onboarding takes over twice as long as promised.** Promised decision in 3 working days, actual median 7 working days, worst cases past 12. (Deborah: "we promise customers a decision in three working days and we are nowhere near it. Our median is seven working days, and the worst cases go past twelve")
- **Large document backlog.** 4,200 documents waiting for an analyst, building since about March after volume rose without headcount growth. (Deborah: "Right now we have 4,200 documents waiting for an analyst.")
- **Business accounts consume disproportionate analyst time.** Business accounts are ~15% of applications but take ~40% of analyst time due to incorporation, directors, PSCs and Companies House checks. (Deborah: "Business accounts. They are only about 15 percent of applications, but they take about 40 percent of my analysts' time.")
- **Seasonal peaks roughly double volume.** January and September peaks roughly double volumes; January peak risk if not fixed. (Deborah: "January and September are our peaks: volumes roughly double.")
- **Manual copy-typing between document viewer and CaseFlow.** Analysts copy-type key fields into CaseFlow because CaseFlow cannot read documents; same address typed up to four times in one case, plus constant screen switching. (Tom: "Honestly, the copy-typing. I've typed the same address four times in one case. And switching between the two screens all day.")
- **Slow per-document handling time.** About six minutes for a clean personal document; twenty minutes or more for a company document. (Tom: "A personal document is about six minutes if it's clean. A company document can be twenty minutes or more, because you're cross-checking directors and owners.")
- **Frequent ask-applicant rework.** About 31 percent of applications get at least one ask-applicant; returns go to the queue and often a different analyst who starts over, driving backlog. (Tom: "About 31 percent of applications get at least one "ask applicant".")
- **Prior OCR pilot failed due to missing confidence signals.** A 2024 OCR pilot was abandoned after four months because every field looked equally confident, forcing full rechecking; trust is damaged. (Tom: "We stopped using it after four months. The problem was that it never told you how sure it was. Every field looked equally confident, so we ended up rechecking everything it did, and that was slower than doing it ourselves.")

## Requirements

- **Solution must surface confidence and provenance.** Analysts will not trust a tool that cannot show where an answer came from or how sure it is. (Deborah: "My analysts will not trust a tool that can't show them where an answer came from.")
- **Assistive, not decision-making: human decides every KYC case.** Tool may prepare, highlight and suggest, but an analyst decides and is accountable. (Helen: "a person must make every KYC decision. A tool can prepare, highlight and suggest, but an analyst decides and is accountable. That is not negotiable.")
- **Full audit trail of decisions and evidence.** Must be able to show a regulator who decided what, when, and on what evidence. (Helen: "Whatever the tool does, we must be able to show a regulator who decided what, when, and on what evidence.")
- **Point directly to the problematic part of a document.** Tom wants the tool to flag which part of a document is the issue so he does not read the whole document. (Tom: "Stop the copy-typing, and show me straight away which part of a document is the problem, so I don't have to read the whole thing to find it.")
- **Target of 3 working days before January peak.** Success is back inside three working days for most customers before January, with analysts actually wanting to use the tool. (Deborah: "If we're back inside three working days for most customers before the January peak, I'll be happy. And if my analysts actually want to use the tool.")

## Constraints

- **Independent model validation required before production.** Any model use needs independent model validation; in practice about three weeks, so plan for it. (Helen: "anything that uses a model needs an independent model validation before it goes into production. In practice that takes about three weeks, so plan for it.")
- **MLRO sign-off for KYC control changes.** Any change to KYC controls needs Helen's sign-off. (Helen: "Any change to our KYC controls needs my sign-off")
- **Customer documents must stay in the UK.** Processing must stay in AWS London region; no public AI chat tools (already blocked for staff). (Helen: "Customer documents must not leave the UK. Our cloud is AWS in the London region, and nothing goes to public AI chat tools.")
- **CaseFlow write access requires vendor change.** CaseFlow API is read-only for the team; writing back needs a vendor change, and the last change took eight weeks. (Tom: "CaseFlow has an API, but it's read-only for us. Writing anything back needs a change from the vendor, and the last change took eight weeks.")
- **Customer data in history export needs Helen's approval.** 18 months of CaseFlow history exists but contains customer data; Helen must agree how an export is handled. (Deborah: "I think so, but it contains customer data, so Helen will need to agree how.")

## Open questions

- **How can the 18-month review history be exported given customer data?** Roughly 61,000 document reviews with decisions and reason codes exist; export method and controls to be agreed with Helen. (Deborah: "I think so, but it contains customer data, so Helen will need to agree how.")
- **How will CaseFlow integration work given read-only API?** Unresolved how the solution writes results back or avoids copy-typing without a vendor change (last change took eight weeks). (Tom: "CaseFlow has an API, but it's read-only for us.")

## Success criteria

| Criterion | Baseline | Target | Measured by | Owner | By |
|---|---|---|---|---|---|
| Median working days from application to decision | 7 working days | 3 working days | CaseFlow timestamps, weekly report, pilot cases only | Deborah Okafor | End of week 6 pilot |
| Minutes of analyst time per application | 22 minutes | 12 minutes | CaseFlow work timer, pilot cases, weekly | Deborah Okafor | Week 6 |
| Share of AI-filled fields the analyst accepts without change | – | 90 % | Logged on every accept or correct click in the review screen | Tom Reyes | Week 6 |
| Share of KYC decisions made by a named analyst | – | 100 % | Decision log: analyst name recorded on every case, weekly check | Helen Achebe | Week 6 |
| Average cost per onboarding application | 11.4 £ per application | 8 £ per application | Finance cost-per-application report, monthly | Martin Hale | March |

## First use case

**Proof-of-address check** (score 83.7/100): Read utility bills and statements, extract name, address and date, check them against the application and show the analyst any doubtful field.

Out of scope: Automatic KYC decisions (A person must make every KYC decision (MLRO, 06:50)).
