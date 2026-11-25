# KYC Operations: how we count (MI definitions)

*From Deborah Okafor's MI pack. These are the definitions behind every number the board sees. All data is fictional.*

## Turnaround

**What we report:** the median turnaround, in working days.

- Count **working days** (Monday to Friday, not bank holidays) from the day we receive the application to the day we decide it.
- **Do not count the days we are waiting for the applicant.** When an analyst asks the applicant for something else, the clock stops until the new document arrives.
- Only **decided** applications count: approved or declined. Withdrawn applications and applications still open are not in the turnaround.
- An application counts in the **month of its decision**.
- We always report the **median**, never the average: a few very slow business cases would make an average meaningless.

In CaseFlow: `working_days_open - applicant_wait_days`, for `status` approved or declined, by `decided_at`.

Our promise to customers is a decision within 3 working days. In October 2026 our median was 7.

## Backlog

**What we report:** the documents waiting for an analyst, right now.

- Count **documents**, not applications. One business application can have six documents waiting.
- A document is waiting when it has **not been reviewed yet** and its application's status is **open** (in the analysts' queue).
- Applications **waiting for the applicant** are not backlog: the next step is theirs. Applications **with Financial Crime** (escalated) are not backlog either: they are not waiting for a KYC analyst.
- Documents on withdrawn applications are never backlog.

In CaseFlow: documents with no `reviewed_at`, on cases with `status = 'open'`.

At the end of October 2026 the backlog was about 4,200 documents.

## Ask-applicant rate

The share of applications with at least one document whose outcome is `ask_applicant`, out of all applications received in the period. This one is already in the semantic layer as the metric `ask_applicant_rate`.
