**My decision: yes, the team is worth its cost here, but not because it is more accurate.**

**What the numbers say (live model `deepseek/deepseek-v4-flash`, all 19 cases, both designs):**
- **Accuracy is tied.** Both get 19/19 decisions, 19/19 missing items, 3/3 injection cases handled, and no unsafe miss.
- **The team costs less money, not more.** 14,362 tokens per case against 24,949 for the single agent, so $0.029 against
  $0.047 for the whole run (about **40% cheaper**). Each specialist has a short prompt and few turns; the single agent's
  conversation keeps growing as it makes 9-14 tool calls (it re-asks for things it already has).
- **The team costs more calls and time.** 8.1 model calls per case against 5.6 (**1.45 times**) and 36 seconds against 27
  (**34% slower**). Running documents and finance at the same time saved 8% (136.6 s against 125.1 s on four cases).
- **The team is cleaner.** The trace review found 3 problems with the single agent and none with the team, because the
  team's reviewer checks every result against its evidence and the decision is derived by code.
- *(Earlier, on the offline stand-in, the team looked about twice as expensive in calls. Live, the extra calls are cheap
  because they are small; that is why I stopped trusting the offline number for cost.)*

**Why yes.** Money is not the cost of the team here: time is, and a third more seconds on a task that already waits days for
a human is cheap. What the team buys is *structure that fails safely*: least-privilege tools per specialist, checked handoffs,
a reviewer that cannot be talked into agreeing, and a decision that is never a model's choice. The single agent matched it on
accuracy only after I added the same kind of guard (the `Assessment` contract refuses a decision that contradicts its flags),
and the live runs showed why that was needed.

**What I would still change.** Documents, compliance and finance are three plain tool-callers; merging them into one agent
would save model calls without losing the reviewer, states or gate. Intake (the only model that reads untrusted text) and the
follow-up writer (no tools) are the two I would never merge. And one live miss is worth remembering: in the first live team run
the intake agent probed for reply files that did not exist (`REQ-003-R1`), hit the tool-error limit and stopped the case with no
decision. The system did the right thing (it stopped and asked a person), and a sharper instruction fixed it, but it shows the
failure mode of an agent team: more agents, more places for a model to wander.
