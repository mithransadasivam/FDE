# Scoring one case of the crash test

*From Helen Achebe (MLRO). Every write the bank holds is counted from the bank's own records, not from the workflow's log.*

A case passes when all five checks pass.

| Check | Passes when |
|---|---|
| **end** | The workflow ended the way the plan expects: `completed`, `recorded`, `escalated`, `rejected`, `expired` or `stopped` |
| **messages** | The contact gateway holds exactly the expected number of requests and of reminders for the case |
| **caseflow** | CaseFlow Classic holds exactly the expected number of outcomes for the case, and the exception exactly the expected number of "Outcome recorded" comments |
| **escalation** | The exception holds exactly the expected number of "Escalated to" comments |
| **agent_once** | The agent finished once per round: a crash may cut a run short, but no round has two finished agent runs (a crash while the case waits must never make the agent work it again) |

A case whose crash was armed but never fired is reported, but scored all the same: say so in your report.
