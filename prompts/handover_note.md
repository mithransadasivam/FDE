# prompts/handover_note.md

Purpose: turn a long support thread into a handover note for the next shift.
Input: the full thread text, pasted between <thread> tags.
Output: exactly three "- " bullets: what the customer reported, what was tried and the result, the single next step.
Model: hosted backend, temperature 0.

## Template
Identical to prompts/handover_note_v4.txt (the version that was scored):

You are an IT support engineer writing a shift handover.
Summarise the thread below in exactly three bullets, one per line, each starting with "- ":
1. What the customer reported, including any job ID or ticket number they gave
2. What has already been tried and the result
3. The single next step for the incoming engineer
Use only what the thread says. Do not invent job IDs, causes or fixes.
If the thread shows the issue is fixed and the customer confirmed it, bullet 3 is "- close the ticket".
If the next step is unclear, write "- next step unclear" as bullet 3.
Output the three bullets and nothing else.

<thread>
{text}
</thread>

## Current version: v4   Score: 10/10 cases, 100% of points on data/handover_note_tests.csv (2026-09-30)
## History
Checklist scoring, claude-haiku-4.5, temperature 0. Test data first fixed to accept "re-run" wording, which lifted v1 from 90% to 93%.
v1 bare 8/10 (93%) | v2 +"keep identifiers as written" 8/10 (93%, no gain, not kept) | v3 +closure rule (v1 base) 9/10 (97%) | v4 +job ID in bullet 1 10/10 (100%)
Stopped at 10/10: nothing left to gain on this set.
## Known failures
- v2 shows a general "keep identifiers" instruction is ignored, while naming the job ID in the bullet 1 line worked. Only one test case carries an ID, so this is thin evidence.
- Not covered by the 10 cases: a thread with two unrelated issues (only the VPN + printer case, which passes), very long threads, threads in which the customer contradicts the agent.
- The ten cases are short and invented; real threads are longer and messier.
