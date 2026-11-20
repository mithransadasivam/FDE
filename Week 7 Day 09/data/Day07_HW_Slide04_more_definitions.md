# KYC Operations: more definitions (homework)

*The rest of Deborah's MI pack, for the harder questions. All data is fictional.*

## Financial year

The bank's financial year runs from **1 April to 31 March**. "This financial year" is FY2026/27, which started on 1 April 2026. Quarters count from April: Q1 is April to June, Q4 is January to March. `caseflow.calendar` has `financial_year` (FY2026/27) and `financial_quarter` (FY2026/27 Q1) for every day. A plain "Q3 2026" in a question still means the calendar quarter, July to September.

## Last week

The last full week, **Monday to Sunday**, before the extract day. The extract ran on Friday 30 October 2026, so last week is 19 to 25 October 2026. Not "the last 7 days".

## Per working day

A rate "per day" or "a day" divides by the **working days** in the period (`caseflow.calendar.is_working_day`), never by calendar days. For a period that runs past 30 October 2026, count working days up to 30 October only: there is no data after it.

## First-time right

A decided application (approved or declined) is first-time right when it was **approved and no document on it was ever asked again** (no outcome `ask_applicant`). The rate is first-time-right applications over decided applications, in the month of the decision.

*Not agreed yet: when we compare analysts, which analyst an application counts for. The MI team is to confirm.*

## Within the promise

A decided application is within the promise when its **turnaround** (see the MI definitions) is **3 working days or fewer**.

## Overdue

An application not yet decided, and not waiting for the applicant (status `open` or `escalated`), that has been with us for **more than 3 working days**, not counting days waiting for the applicant.

## Counting applications across documents

A question about applications that joins to `caseflow.documents` must count each application once: `COUNT(DISTINCT case_id)`. A join gives one row per document.
