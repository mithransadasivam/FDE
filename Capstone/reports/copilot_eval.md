# Copilot evaluation

**Result: PASS**  
Date: 2026-10-30T02:00:06+00:00  
Run: fake models (simulated); models: openrouter/anthropic/claude-haiku-4.5  
Settings: {"speed": 4.0, "within_seconds": 2.0, "interviews": [1, 2, 3, 18], "mode": "fake"}

## Pass rule
Every forbidden question must be warned within 2 seconds of the question ending. Warned: **4 of 4**; slowest warning **0.031 s** after the question ended.

## Caught out of planned
| moment | caught | planned |
|---|---|---|
| forbidden_question | 4 | 4 |
| cv_conflict | 4 | 4 |
| vague_answer | 4 | 4 |
| good_technical_answer | 4 | 4 |
| behavioural_answer | 4 | 4 |

## Warning time (seconds after the forbidden question ended, on the interview's own timeline)
Average **0.0255 s**, slowest **0.031 s**. This is the time the copilot needed after the question ended; a live deployment adds the speech-to-text delay on top.

## False alarms
Warnings where no forbidden question was planned: **0**. CV-check cards where no conflict was planned: **0**.

## By interview
| candidate | forbidden_question | cv_conflict | vague_answer | good_technical_answer | behavioural_answer | false alarms |
|---|---|---|---|---|---|---|
| 1 | yes | yes | yes | yes | yes | 0 |
| 2 | yes | yes | yes | yes | yes | 0 |
| 3 | yes | yes | yes | yes | yes | 0 |
| 18 | yes | yes | yes | yes | yes | 0 |

## Limits
- The practice interviews are scripted and fictional: the copilot is tested on moments we planned, in clean text. Real, unplanned interviews will be harder (accents, overlap, speech-to-text errors); test those with a person scoring the copilot's cards.
- Ran in fake mode (rule-based) at 4x. A missed moment can mean the key words did not match, not that it was missed by a person.
