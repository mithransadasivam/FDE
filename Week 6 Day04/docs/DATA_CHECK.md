# Data check: does the data back up what we heard?

*All numbers come from `scripts/check_story.py`, run on `data/Day01_HW_Slide03_review_history.csv` (5,002 reviews, 1,713 applications, 5 Oct to 2 Nov 2026) and `data/Day01_HW_Slide03_backlog_export.csv` (4,200 documents). One case_id counts as one application.*

| # | What we heard | Who | What the data says | Verdict |
|---|---|---|---|---|
| 1 | Business accounts are about 15% of applications | Deborah | 16.9% of applications (290 of 1,713 are business) | confirmed |
| 2 | …but take about 40% of analyst time | Deborah | 46.9% of analyst minutes (19,855 of 42,328) | partly: the real share is higher than said |
| 3 | 31% of applications get at least one "ask applicant" | Tom | 29.1% (498 of 1,713 applications) | confirmed |
| 4 | A personal document takes about 6 minutes, a company document 20 or more | Tom | Personal: 6.4 min on average. Business: 13.6 min on average (median 12.7) | partly: personal is right; business is about 14 minutes, not 20+ |
| 5 | A resubmitted document takes longer, because the case starts again | Tom | 11.1 min against 8.1 min for a first submission (+37%) | confirmed |
| 6 | 4,200 documents are waiting | Deborah | 4,200 in the export. 1,652 (39.3%) have waited more than 3 working days; 2,092 have waited 3 or more. Median wait is 2 days, longest 14 | confirmed |

Two things worth noting. In claim 4 the business figure is an average over all business document types (a passport costs far less than a directors' register), so Tom's "20 or more" may describe the hardest company documents rather than the average. And Deborah's median of 7 working days for a full decision is about the whole application, so it is not the same thing as the 2-day median wait of a document in the backlog.

## The top three reasons for "ask applicant"

Out of 568 reviews that ended in "ask applicant":

1. **Blurred image**: 236 (41.5%)
2. **Proof of address older than 3 months**: 158 (27.8%)
3. **Name mismatch**: 92 (16.2%)

(Then missing page 47, 8.3%, and other 35, 6.2%.) Tom named the three reasons in the interview, in a different order: he put the old proof of address first. By count, blurred images come first.

## One thing the data shows that nobody said in the interview

**Branches cause most of the "proof of address older than 3 months" requests, far more than their share of the work.**

- Branches handle 24.1% of all reviews, but 58.2% (92 of 158) of the "older than 3 months" requests come from branch applications. The app handles 75.9% of reviews but only 41.8% (66) of those requests.
- This is specific to proof-of-address documents. The "ask applicant" rate per review is 21.4% for utility bills at branches against 11.4% in the app, 22.5% against 10.6% for council tax bills, and 18.1% against 8.2% for bank statements. For identity documents the two channels are about equal (driving licence 10.4% in both; passport is lower at the branch, 7.1% against 9.5%).
- Overall, a branch review ends in "ask applicant" 15.3% of the time against 10.1% in the app.

**What it could mean:** a customer at a branch is handing a bill to a person, and the stale date is not being caught at the counter. A simple check at the counter ("is this bill dated in the last 3 months?"), or a reminder in the branch process, could remove a large share of these requests and the rework that follows (a resubmission takes 37% longer), with no AI. It is also a hypothesis, not a proven cause: we have not seen how the branch process works, so the question for Tom and Deborah is why branch bills are older. It costs almost nothing to test.

## How I checked

- Script: `python scripts/check_story.py`. It reads the two CSV files with pandas and prints every number above. It does not write any file.
- One case_id = one application. No case in the review file mixes personal and business documents, so an application's type is unambiguous.
- Claims 1 and 3 are counted per application; claims 2, 4 and 5 are counted per review (minutes are per document review). Minutes cover reading and checking only, as recorded in the review history.
- "Past 3 working days" is read as *more than* 3 days waiting (`working_days_waiting > 3`). Counting 3 days as already late gives 2,092.
- The review file is described as a random sample, so figures are estimates for the whole 61,000-review history, not exact.
- Not checked: the median of 7 working days and the 22% abandonment figure, because neither is in these two files.
