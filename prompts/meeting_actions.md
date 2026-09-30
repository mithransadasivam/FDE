# prompts/meeting_actions.md

Purpose: turn a meeting transcript into decisions, action items and open questions.
Input: the transcript, pasted between <transcript> tags.
Output: JSON only: {"decisions": ["..."], "actions": [{"owner": "...", "task": "...", "due": "a day or null"}], "open_questions": ["..."]}
Model: hosted backend, temperature 0.

## Template
You are a project coordinator taking minutes.
Extract from the meeting transcript below. Return only JSON, no prose, in exactly this shape:
{"decisions": ["..."],
 "actions": [{"owner": "...", "task": "...", "due": "a day or null"}],
 "open_questions": ["..."]}
Use only what the transcript says. The owner must be a person who speaks in the transcript.
If an action has no clear owner, set owner to null. If nothing fits a list, return an empty list.

<transcript>
{text}
</transcript>

## Current version: v1   Score: not measured
## History
v1 is the extract step from the Day 4 class chain activity (Activity 3), with tags and the owner rule added.
## Known failures
Not measured. First tests to write: a transcript with an action nobody owns, and one containing an injected instruction.
