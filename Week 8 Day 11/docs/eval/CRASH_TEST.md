# Crash test: 20 cases, one crash each

*Date: 2026-11-23 · Run as: helen.achebe · Day length: FDE_DAY_SECONDS = 30 (scripted model, FDE_FAKE_LLM=1)*

Every number below is from Workflows → Crash test (`engagement/workflow/crashtest.json`; the two runs are kept in `docs/eval/crash_runs/`). Each case is scored from the bank's own records, not from the workflow's log.

## Result

| Run | Passed | Failed cases | Crashes fired |
|---|---|---|---|
| Before the fix | 18 of 20 | C04 KX-1008, C12 KX-1016 (both: escalation) | 13 of 13 |
| After the fix | 14 of 20 | C01, C05, C06, C16 (messages), C18 (end, messages, agent_once), C20 (agent_once) | 13 of 13 |

**The escalation check failed on 2 cases before the fix and on 0 after it.** The 6 failures after the fix are not a write that happened twice; they are explained below, and I did not get a run on this PC where they were absent. Other runs I made, and why I do not use them: at 10-second days 7 of 20 passed and at 6-second days 5 of 20 (approvals of 30 s and 18 s expired before the test could decide them); a second 30-second run after the fix scored 15 of 20, but the bank's server went down as the run ended, so its last case was scored from an empty answer.

## The write that happened twice

The **"Escalated to …" comment** on the KYC exception, made by the `escalate` step in `backend/app/workflow/steps.py`. KX-1008 (C04) and KX-1016 (C12) each held **2** such comments where the plan expects **1**. Both cases had the crash armed at `after_escalate`: the worker died after the comment was written and before the step was saved, so DBOS ran the step again and wrote the comment a second time. Every other count on those two cases was right (1 request, 1 reminder, 1 outcome, 1 outcome comment, and the agent ran once), so the failure is that one write.

## The fix

The step wrote the comment with `bank.comment_on_exception()`, which sends no `Idempotency-Key`. It now writes it with `writes.post(grants.token_for(key, "kyc-exceptions"), …, writes.idempotency_key(key, DBOS.step_id))`, as the request, reminder and outcome-comment writes already do. The key is `{workflow id}:{step id}`: the same on every attempt of the same step and different for every other write. The second attempt after a crash sends the same key, so the bank replays the first comment and adds nothing. After the fix, KX-1008 and KX-1016 both pass with the crash still firing on both.

To make the crash test run at all I also built the three class tickets this repository had left as stubs: `idempotency_key()` and `already_recorded()` (ENG-1003), `work_round()` (ENG-1001) and `chase()` (ENG-1002). Their tests pass (`test_writes.py`, `test_case.py`, `test_chase.py`; the chase-clock test is timing-sensitive and passes on its own). `score_case()` is in `backend/app/workflow/scoring.py`, with its 5 tests passing.

## The other failures (not double writes)

| Case | What the bank held | What happened |
|---|---|---|
| C01, C05, C06, C16 | 1 reminder, plan expects 0 | The applicant was due to reply on day 1 or 2, before the day-3 reminder, but the worker was restarted about ten times during the run (every armed crash restarts it for all 20 cases) and these cases' waits ran down while it was down, so the reminder went out first |
| C18 KX-1022 | 1 reminder, 2 finished agent runs in round 2, ended `expired` instead of `rejected` | Same lateness; and the round-2 `propose` step ran twice, so two proposals were open and the test's rejection reached only one |
| C20 KX-1024 | outcome and comment correct (1 each), 2 finished agent runs in round 1 | A crash armed for another case interrupted `propose` after the agent had saved its proposal and before the step finished, so the agent worked the case again |

I read these as timing: this PC restarts the worker in 3 to 5 seconds, which is about 0.15 of a 30-second day, but one run restarts it 15 times, and short days make that cost large. I did not show that a longer day removes them: I did not get a clean run at 60-second days.

## Writes that may happen twice

The **Slack message** sent when a case is escalated (`escalate` step). Slack's incoming webhook takes no key. A second copy is harmless and carries no customer name. This is listed in `data/Day10_Slide21_writes.csv` as "At least once (agreed)", with the note that Helen agreed. I did not ask Helen again; this report relies on that existing entry. Every other write is in the same table with its key or marker, and the table matches the code: the escalate comment is now an `Idempotency-Key` write.

The agent's proposal in `propose` can also run twice after a crash (tokens spent twice). It writes no outcome, but in C18 and C20 it left a second finished run and a second approval card, which the `agent_once` check counts. That needs Helen's decision, below.

## What I would test next

1. A crash **inside `propose`**, after the agent has saved its approval and before the step finishes (it cost C18 and C20 their `agent_once` check): either make the approval id depend on the round, so a re-run replaces the first one, or accept it and ask Helen to say so.
2. A **change to the workflow's code while cases are waiting** (rule 18: never change `APP_VERSION` with cases waiting).
3. This test crashes the worker for all 20 cases at once, so one case's crash disturbs the others. Run the crash point **alone for one case** to separate the crash being tested from the collateral.

## What this report does not show

No run scored 20 of 20. The tests I ran: the backend suite and the workflow tests named above. I did not run the end-to-end (Playwright) tests: another session was using the ports, and I stopped before running them. I did not do the by-hand KX-1004 check on the Workflows page (start, approve, crash on day 2), so the reminder-on-day-3 and escalation-on-day-7 timing after a crash is covered only by `test_chase.py`.
