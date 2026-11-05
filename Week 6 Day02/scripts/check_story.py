"""Check what the client told us against the bank's own data (Day 1 homework, Task 1).

One case_id = one application. Read-only: never writes to data/.
Run:  python scripts/check_story.py
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
rev = pd.read_csv(DATA / "Day01_HW_Slide03_review_history.csv")
bl = pd.read_csv(DATA / "Day01_HW_Slide03_backlog_export.csv")


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


print(f"Reviews: {len(rev):,} | applications: {rev.case_id.nunique():,} | backlog: {len(bl):,}")
print(f"Review dates: {rev.review_date.min()} to {rev.review_date.max()}\n")

# 1. Business share of applications (an application's type is its account_type)
app_type = rev.groupby("case_id").account_type.agg(lambda s: s.mode().iat[0])
mixed = (rev.groupby("case_id").account_type.nunique() > 1).sum()
print(f"1. Business share of applications: {pct((app_type == 'business').mean())}  (cases with mixed type: {mixed})")

# 2. Business share of analyst minutes
mins = rev.groupby("account_type").minutes_spent.sum()
print(f"2. Business share of analyst minutes: {pct(mins['business'] / mins.sum())}  ({mins['business']:.0f} of {mins.sum():.0f} min)")

# 3. Applications with at least one ask_applicant
ask = rev.groupby("case_id").outcome.apply(lambda s: (s == "ask_applicant").any())
print(f"3. Applications with >=1 ask_applicant: {pct(ask.mean())}  ({ask.sum():,} of {len(ask):,})")
print("   Outcomes by review:", rev.outcome.value_counts().to_dict())

# 4. Minutes per document, personal vs business
avg = rev.groupby("account_type").minutes_spent.agg(["mean", "median"]).round(1)
print(f"4. Minutes per document:\n{avg.to_string()}")

# 5. Resubmissions
rs = rev.groupby("resubmission").minutes_spent.mean().round(1)
print(f"5. Mean minutes, resubmission no vs yes: {rs['no']} vs {rs['yes']} ({pct(rs['yes'] / rs['no'] - 1, 0)} longer)")
print(f"   Resubmissions are {pct((rev.resubmission == 'yes').mean())} of reviews")

# 6. Backlog
over3 = (bl.working_days_waiting > 3)
print(f"6. Backlog: {len(bl):,} documents; waiting >3 working days: {over3.sum():,} ({pct(over3.mean())}); >=3 days: {(bl.working_days_waiting >= 3).sum():,}")
print(f"   Median wait {bl.working_days_waiting.median()} days, max {bl.working_days_waiting.max()}")
print(f"   Business share of backlog: {pct((bl.account_type == 'business').mean())}")

# Top reasons for ask_applicant
a = rev[rev.outcome == "ask_applicant"]
print("\nTop ask_applicant reasons (reviews):")
rc = a.reason_code.value_counts()
print(pd.DataFrame({"n": rc, "share": (rc / len(a) * 100).round(1)}).to_string())

# Nobody-said: reasons by channel and doc type
print("\nShare of all reviews by channel:", (rev.channel.value_counts(normalize=True) * 100).round(1).to_dict())
print("\nReason x channel (counts):")
print(pd.crosstab(a.reason_code, a.channel, margins=True).to_string())
print("\nReason x channel (share of that reason coming from each channel, %):")
print((pd.crosstab(a.reason_code, a.channel, normalize="index") * 100).round(1).to_string())
print("\nAsk-applicant rate by channel (per review):")
print((rev.assign(ask=rev.outcome == "ask_applicant").groupby("channel").ask.mean() * 100).round(1).to_string())
print("\nReason x doc_type (counts):")
print(pd.crosstab(a.reason_code, a.doc_type, margins=True).to_string())
print("\nAsk-applicant rate by doc_type x channel (%):")
print((rev.assign(ask=rev.outcome == "ask_applicant").pivot_table(index="doc_type", columns="channel", values="ask", aggfunc="mean") * 100).round(1).to_string())
