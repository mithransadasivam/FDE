# Does the fact-checker earn its place?

Name: Mithran Sadasivam   Date: 2026-10-15

## The fact-checker

- What it checks (one sentence): every checkable claim in the draft notice (times, numbers, causes, who is affected, what staff must do, promises) against the research notes, and it lists each claim the notes do not support.
- Where it sits in the team, and where its findings go: between the writer and the reviewer (`app/fact_checker.py`). If it lists unsupported claims, the supervisor sends the draft back to the writer with those claims as feedback, while `revisions < MAX_REVISIONS`; a clean draft (or one where the revisions are used up) goes on to the reviewer.
- Its prompt's most important line, and why: "A claim is unsupported when no fact in the notes says it, or when it goes further than the notes (a made-up time, a guessed cause, a number of people, an estimated fix time, a promise)." Writers invent in exactly these ways, so naming them makes the checker look for them. The line "Do not judge style" keeps it from doing the reviewer's job.

## The comparison

Topics file used: `data/my_notice_topics.csv` (the 3 class topics plus 2 of my own: PRN-310 stuck print jobs, and WIFI-102 Wi-Fi failures after a password change).

The model is not deterministic and the shared model account allows 20 requests a minute, so the first run needed re-running for VPN and Wi-Fi (see "What went wrong with the runs" below). Each row below is a pair that finished in the **same** run, except VPN (see the note under the table).

| Topic | Version | Calls | Tokens | Seconds | Revisions | Automatic problems | Unsupported claims you found by reading |
|---|---|---|---|---|---|---|---|
| Finance Portal outage | team | 5 | 12,460 | 83.3 | 0 | 0 | 1: "This is due to a 503 error" (the notes say what a 503 means, not that it is the cause) |
| | team + checker | 11 | 18,126 | 160.3 | 2 | 1 (missing: status page) | 0, but the actions line is off topic and the notice lost "follow the status page" |
| VPN-809 (returning from leave) | team | 7 | 15,518 | 124.2 | 1 | 0 | 0 |
| | team + checker | 11 | 19,327 | 91.0 | 2 | 0 | 1: "there are no open tickets related to this issue" (the help desk data has 5 unresolved VPN-809 tickets) |
| Company Mail delays | team | 7 | 15,201 | 71.6 | 1 | 0 | 1: "This affects all staff sending emails to external recipients" |
| | team + checker | 8 | 16,071 | 72.0 | 1 | 0 | 0 |
| Print jobs, PRN-310 (own) | team | 9 | 17,297 | 78.3 | 2 | 1 (missing: Print Queue) | 0 |
| | team + checker | 11 | 22,608 | 132.9 | 2 | 0 | 0 |
| Wi-Fi, WIFI-102 (own) | team | 9 | 17,089 | 60.6 | 2 | 0 | 1: "there are no open tickets related to this issue" (INC-1032 and INC-1012 are open) |
| | team + checker | 13 | 22,014 | 82.3 | 2 | 0 | 2: "use the 'Fix Wi-Fi' tool in the IT portal" (invented tool; the article says the device management app); "No further updates are planned unless the situation changes" |

**Totals over the four topics where both versions finished in the same run (Finance, Mail, Print, Wi-Fi):**
team 30 calls, 62,047 tokens, 293.8 s. Team + checker 43 calls, 78,819 tokens, 447.5 s.
Automatic problems 1 vs 1. Unsupported claims found by reading (these four topics): 3 vs 2.

**Totals, all five topics** (VPN taken as team from run 1, team + checker from run 3):
team 37 calls, 77,565 tokens. Team + checker 54 calls, 98,146 tokens.

**Extra cost (four matched topics): +13 calls (+43%), +16,772 tokens (+27%), +153.7 s (+52%).** With VPN included: +46% calls, +27% tokens.

**What went wrong with the runs (reported, not hidden):** 6 attempts at the VPN topic: the team without the checker finished only 1 of 3 (the other two stopped with "researcher handoff failed: not valid JSON") and the team with the checker finished 2 of 3 (one stopped the same way). Wi-Fi failed once for the checker version for the same reason. This is the researcher, which both versions share, so it is not the checker's doing and it is not an argument for or against it. A likely cause is the 300-token reply limit cutting the researcher's JSON off; I did not change that. Raw logs: ``docs/evidence/team_comparison_all_runs.jsonl` (all 16 rows, every notice), and `logs/compare_fact_checker_output_*.txt`.

Also: the very first attempt crashed on an OpenRouter 429 (rate limit) and showed 0 tokens. I fixed both in `app/rag.py` (the Day 6 model wrapper: it now passes token counts on and waits and retries on a 429). `app/team.py` was not changed for the fact-checker.

## What it caught, and what it missed

- One unsupported claim the checker caught (quote it): in a traced Finance Portal run (`logs/fact_check_trace.txt`) the writer's second draft said "Several users have reported this issue." The checker flagged it: "No fact in the notes mentions user reports." The writer removed it. In the same trace it also caught "IT is working on the issue." and, in the Company Mail run, "Updates will be posted on the service status page." (no fact says so), and these were fixed before the reviewer saw the draft.
- One problem it missed or flagged wrongly:
  - **Missed:** in the WIFI-102 notice that passed the checker, the writer told staff "On managed laptops, use the 'Fix Wi-Fi' tool in the IT portal". No fact mentions that tool (KB-4401 says "the device management app"), and the same notice says "No further updates are planned unless the situation changes", a promise that is also not in the notes. I found both only by reading. It was also inconsistent: in the Finance trace it flagged "affecting all users" in draft 1 but accepted "This affects all staff who use the portal" in draft 3.
  - **Flagged wrongly (too strict):** in the Print trace it flagged "Some print jobs are stuck in the queue with error PRN-310" because the notes only give ticket counts. That is a fair reading of the notes, and it costs a revision for little gain.
  - **Cannot catch by design:** "there are no open tickets related to this issue" appeared in the VPN and Wi-Fi notices. It contradicts the help desk data, but the researcher's notes said it, so the checker (which only compares the draft with the notes) agreed.

## Decision

Keep the fact-checker? **Only for some notices: keep it for notices sent to all staff, skip it for low-stakes internal drafts.** It costs about 43% more calls, 27% more tokens and 52% more time over four topics, and the automatic checks scored 1 problem for both versions, so on those checks alone it earns nothing. What it does is remove made-up details a person would otherwise have to find (user reports, promises of updates, "IT is working on it") before review, and a wrong detail in a notice to everyone costs far more than 27% more tokens. But it is a first filter and not a guarantee: it missed an invented tool and a promise, flagged some claims too strictly, and cannot see errors in the research itself, so the person approving must still read every notice and check the facts the notes got wrong (for example, "no open tickets" when there are open ones).
