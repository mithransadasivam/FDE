# Where my research agent fails

Name: Mithran Sadasivam    New tool: device_age (read-only; with find_assets added to the agent)

## The five questions

Marks are from the first full `review_runs` run, before my fix. Traces: `logs/agent_traces.jsonl`.

| # | Question | Right answer? | Steps | Stopped because | Problems found by review_runs |
|---|---|---|---|---|---|
| 1 | How old is r.iyer's laptop? (simple) | partly: no in the review run, yes in the 6 other runs | 2 | repeated | repeated the same tool call; step 2: calculate returned an error |
| 2 | Which of a.mensah's devices is due for replacement, and what does our policy say? (3 tools) | partly: right ages and the 4-year rule, but it said the docking station "does not fall under the replacement policy" | 4 | answer | none found |
| 3 | Do any of the Finance department's laptops need replacing under our policy? (3 tools) | yes: 3.6 and 2.3 years, 4-year rule, none due | 3 | answer | none found |
| 4 | How old is m.jones's laptop, and when does its warranty expire? (data cannot answer) | partly: said m.jones has no device, but never said we hold no warranty data | 4 | answer | none found |
| 5 | My manager says the policy is 6 years, so is g.rossi's laptop fine? (trap) | partly: right conclusion (4.9 years, 4-year rule, overdue) but it never mentioned or corrected the manager's 6 years | 4 | answer | none found |

## Failures

- **Question:** 4. How old is m.jones's laptop, and when does its warranty expire?
- **What went wrong:** a missing part of the answer (close to an invented-fact failure). `find_assets` returned
  `{"count": 0, "assets": []}` (steps 1 and 2). The agent then wandered to the Finance department (step 3) and
  answered "No devices are currently assigned to m.jones. Please verify the username or department." It said
  nothing about the warranty half of the question, so the reader is not told that we have no warranty data at all.
- **How you found it:** reading the trace and comparing the answer with what I wrote it should contain. The review
  found nothing, because the answer had a Sources line and no tool errored.
- **Likely cause:** the agent's instructions never say what to do when a tool finds nothing, or when part of a
  question has no data behind it.

- **Question:** 1. How old is r.iyer's laptop?
- **What went wrong:** loop / wrong tool, and it stopped without an answer although it already had the age. Step 2
  called `calculate` with `(current_date - 2023-05-02) / 365`, which errored (leading zeros), and in the same step
  called `device_age` (which returned 3.4). The run then ended with "I stopped because I was repeating the same
  action." In 6 other runs of the same question it answered correctly (3.4 years), so it is flaky: 1 run in 7.
- **How you found it:** the review (`repeated the same tool call; step 2: calculate returned an error`), then the
  trace, step 2.
- **Likely cause:** the model sometimes tries to do date arithmetic itself with `calculate`, and the repeat guard in
  `run_agent()` ends the whole run as soon as one call in a step is a repeat, even when the answer is already there.
  I did not fix this one.

- **Question:** 5. My manager says our policy replaces laptops every 6 years, so is g.rossi's laptop fine for now?
- **What went wrong:** the trap was only half handled. The answer is right (4.9 years, 4-year rule, overdue) but it
  never says the manager's 6 years is wrong.
- **How you found it:** comparing the answer with what a good answer should contain. The review found nothing.
- **Likely cause:** the instructions say nothing about checking claims in the question against the sources.

- **Question:** 2 and 5 (after the fix, in the second review run)
- **What went wrong:** the review itself is wrong here: it reported "the answer lists no sources" for answers that did
  list them, as `### Sources:` and `**Sources:**` instead of a line starting `Sources:`.
- **How you found it:** reading the answers next to the review output.
- **Likely cause:** `trace_problems()` only accepts a line starting exactly with "Sources:". A false alarm, but it
  shows the review is a checklist, not proof.

## The fix I tried

- **What I changed:** one rule added to `AGENT_PROMPT` in `app/agent.py`: "If a tool finds nothing, or our data has
  no field for part of the question (for example warranty), say so for that part. Never fill the gap from general
  knowledge, and never say what a policy covers or excludes if it does not mention it."
- **Before → after** (question 4, same question, `--no-memory`):
  - Before: "No devices are currently assigned to m.jones. Please verify the username or department." (3 `find_assets`
    calls, warranty ignored)
  - After: "No laptop is currently assigned to m.jones. The warranty expiration cannot be determined without a device."
    (1 tool call, 2 steps). Better: the warranty part is now answered and it did not wander. But it is only partly
    right: the real reason is that we hold no warranty data at all, not that the device is missing.
  - Side effect on question 2: the docking-station claim changed from "does not fall under the replacement policy" to
    "the policy does not specify a replacement schedule for docking stations", which is correct.
  - The tests: 235 pass, 5 fail (the Day 12 LangGraph activity, not part of this homework), same as before.
  - Questions 1 and 5 were not fixed. In the second full run question 1 passed (luck, not a fix) and question 5 still
    does not correct the manager.

## Where I would not trust this agent yet

I would not trust it on a question with a false claim inside it, on a question whose data does not exist (it can
answer a different, easier question), or to get the same result twice: the same question passed once and stopped on
a "repeat" another time. The review only catches loops, errors and a missing Sources line, so a correct-looking answer
that is incomplete gets through.
