**My decision: partly.** Keep the parts of the team that are code; use only some of the agents.

**What the numbers say.**
- *Measured, offline baseline (same rules, rule-based stand-in for the model):* both designs get 19/19 decisions, 19/19 missing
  items, 3/3 injection cases and no unsafe miss. The team needs **8.0 model calls per case against 3.9** for the single agent
  (152 against 75), about **2.05 times as many**, for the same tool calls (128) and about the same tokens (60k against 63k:
  each specialist prompt is small, but there are more of them).
- *Measured, live model, single agent only (three runs):* 19/19, then 18/19 with one unsafe miss (the skip-the-checks email),
  at about **5.7 model calls, 26,000 tokens, 18 seconds and $0.03 per case**. The trace review found 11 problems in run 1 and 1
  in run 2.
- *Not measured:* the team on the live model. The OpenRouter key reached its $10 limit (see the Part 1 section), so
  `python -m scripts.compare --llm live` could not run. Reading the offline numbers across, I would expect the team to cost
  roughly twice the model calls per case, with latency growing by a handful of sequential model turns (parallel checks
  recover some of it); that is an expectation, not a measurement.

**Why only partly.** In my cases the team was not *more accurate* than the single agent: it was *safer by construction*.
The thing that made it safe is not that there are several agents. It is three pieces of ordinary code around them: a reviewer
that re-derives every result from the tool evidence, a decision that is computed from that evidence under policy §7 instead of
chosen by a model, and a state machine and gate that no model can talk past. The one live failure I saw (the single agent
flagged the injection and still recommended approval) was fixed by putting a code check on the single agent's answer
(`Assessment` refuses a decision that contradicts its own flags), not by adding agents.

**So I would ship:** one planning agent with the code reviewer and the contract check, the explicit states, the approval gate
and the audit trail, and keep two separate specialists only where separation pays for itself: **intake** (the only model that
reads untrusted email text, so a compromised reading cannot call the check tools) and the **follow-up writer** (no tools at all).
Documents, compliance and finance are three small tool-callers with no judgement in them; splitting them roughly doubles the
model calls and adds three more places for a handoff to fail. The team earns its cost if the workflow grows (new check types
owned by different people, parallel checks at higher volume); at 19 cases and six checks it does not.
