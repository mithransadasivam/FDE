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

## Current version: v1   Score: not yet measured
## History
v1 bare template, scored in Task 2.
## Known failures
Not yet measured.
