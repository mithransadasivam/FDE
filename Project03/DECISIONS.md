# DECISIONS

The brief lists "decisions you must make yourself" in each phase. Here they are, with the reason and where they live in the code.

## Phase 0: how I read the policy where it is unclear

| Rule | How it is read | Where |
|---|---|---|
| 3.1 "within 15 minutes of each other" | Alerts of one service chain together: each alert joins if it is within 15 minutes of the *previous* alert of that service. (S04's six alerts span 12 minutes.) | `triage.group_alerts` |
| 3.2 "within 10 minutes" | A service and a service it depends on (directly or through others) merge if **any pair of their alerts** is within 10 minutes. | `triage.group_alerts` |
| 3.2 root cause | Among the alerting services in the incident, the ones that depend on no other alerting service in it. If several, the one most others depend on, then the earliest. S03: `db-core`, even though `storage-san` is further down, because it did not alert. | `triage.root_cause` |
| 2.2 "three or more services affected" | Distinct services with at least one non-info alert in the incident. S03 has four. | `triage.severity_of` |
| 2.5 / 3.4 flapping | Every firing alert has a matching `resolved` alert within 15 minutes, and the last alert for each check is `resolved`. | `triage.is_flapping` |
| 5.3 freeze | Applies to a change on a **tier-1** service (that is why S09, tier 2 on a Saturday, needs one approval), and is judged at the time the incident opened, so a replay of last week's data gives the same answer every time. | `triage.in_freeze`, `approvers_for` |
| 5.2 + 5.3 together | If both apply, the duty manager is counted once. Two people at most. | `approvers_for` |
| 6.1 "same symptom" | Each monitoring check maps to the words past incidents use (`disk_space` to "disk space"). Score: root-cause match 4, only the service matches 2, symptom 3, same severity 1; it must reach 4. | `triage.similar_incident` |
| 4.4 "do not recommend a step that needs something you do not have" | A step whose text says "Needs … first" (RB-04 step 3, a capacity ticket) is never accepted from the model. | `catalog.Step.needs_prerequisite`, `crew.verify` |

I checked S03, S07 and S10 against `data/scenarios.csv` by running the rules; all three matched, and so did the other seven.

## Phase 2: the line between rules and the model, and what happens when the model is wrong

- **The line (also in `CLAUDE.md`):** *code decides every number and every permission* (grouping, root cause, severity, status, approvals, who may act, what a tool may do); *the model only writes and recommends* (the summary, which runbook step fits, the reason, the status draft), and code checks what it recommends before anyone sees it.
- **A recommendation that fails the check:** the Verifier names the problem, the Planner gets **one retry** with that problem in the prompt, and if it fails again the incident stops as **NEEDS_PERSON** with the reason. A model outage does the same. Rules still group and score everything.

## Phase 3: what `/ready` checks

The database (it can read the catalogue), the runbook index (8 runbooks loaded and indexed), and the model connection (a cheap `GET /models`, cached 15 s). `/health` only says the process is up. When the model is unreachable `/ready` returns 503, status and fact questions still work, and briefs fall back to NEEDS_PERSON.

## Phase 5: speed and cost

- **Safe without a model:** questions whose answer is a row, a count or a filter in our own tables: a service's status, which incidents are open, owner, dependants, tier, on-call, the freeze window, alert counts, the longest past P1, and which steps of a runbook need approval. **Not safe:** anything that summarises, explains why, compares or drafts. The first version sent "Which steps in RB-07 need approval?" to the small model and it said "steps 2 and 3" (it is 3 and 4), so it became a data question.
- **Cache lifetime: 60 seconds.** Status changes every minute in an operations tool; a minute is long enough to absorb repeated questions during a P1 and short enough that nobody acts on a stale answer. The key also contains the prompt version, the model and the latest alert time for the services in the question, so a new alert makes it miss. Status questions are never cached: they are free.
- **Checking answers did not get worse:** ten fixed questions, each with the facts the answer must contain, asked with routing and cache off and then on (`scripts/answer_check.py`). It found two regressions and one bad choice of small model; all three are fixed and the result is in `PERF_REPORT.md`.

## Phase 6: what the engineer sees for a flagged alert

**Both:** a warning ("instructions in alert text were ignored", with the reasons) *and* the original text as inert quoted text in a collapsed panel, with secrets and personal data still hidden. The model sees neither: its copy says the text was withheld. An engineer should be able to see what was in the alert; a model should never be handed it.

## Phase 7: what an approver sees, and never sees

**Sees:** the alerts as the model saw them (hidden values shown as `SECRET` and `UK_MOBILE` chips), the [READ] findings, the one recommended step on one service, the reason, the similar past incident, the policy sections that set the severity and the approvals, who else must approve and who already has.
**Never sees:** a password, a token, a personal mobile (none is in the database the app can read), the model's prompts, or another team's approval reasons beyond the status. The approver cannot edit the step: they approve or reject exactly what is shown.

## Phase 9: classification and the first risk

- **Category: limited risk, Article 50(1).** Not prohibited (Article 5), not high-risk (not Annex I; not Annex III, because it decides nothing about people and is not a safety component of critical infrastructure). The "Ask the tower" chat talks to people, so the AI notice is on screen. *"It helps people at work but does not decide anything about them: does that matter?"* Yes, it is the deciding fact: the Annex III employment entry is about what a system does to a person, not about employees being the users. See `governance/classification.md`, which also lists what would change the answer.
- **Risk to show the duty manager first: R05, the approver is not who they say they are.** The whole design rests on "a person approves every change". In this build the approver is a name chosen from a list. Until approvals come from single sign-on and are signed, that sentence is only as strong as that list. R01 (T08) is accepted because the approval step stands behind it; R05 is the one with nothing behind it.
