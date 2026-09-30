# prompts/handover_note.md

Purpose: turn a long support thread into a handover note for the next shift.
Input: the full thread text, pasted between <thread> tags.
Output: exactly three "- " bullets: what the customer reported, what was tried and the result, the single next step.
Model: hosted backend, temperature 0.

## Template
You are an IT support engineer writing a shift handover.
Summarise the thread below in exactly three bullets, one per line, each starting with "- ":
1. What the customer reported
2. What has already been tried and the result
3. The single next step for the incoming engineer
Use only what the thread says. Do not invent job IDs, causes or fixes.
If the next step is unclear, write "- next step unclear" as bullet 3.
Output the three bullets and nothing else.

<thread>
{text}
</thread>

## Current version: v1   Score: 90% of expected points, 8/10 cases fully right on data/handover_note_tests.csv (2026-09-30)
## History
v1 template above (file: prompts/handover_note_v1.txt) 8/10 (points 90%, checklist scoring, claude-haiku-4.5, temperature 0)
## Known failures
- Drops identifiers: the EXP-4471 job ID given in the thread is missing from the note (the prompt says not to invent IDs but never says to keep real ones).
- Resolved thread: bullet 3 says "No further action needed" instead of naming closure as the next step; the note also said "re-run", a wording the test's alternatives did not list (a test-set gap, not a model miss).
