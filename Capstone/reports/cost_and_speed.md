# Cost and speed

**Result: PASS**  
Date: 2026-10-30T02:12:05+00:00  
Run: fake models (simulated); models: openrouter/anthropic/claude-haiku-4.5  
Settings: {"measured_run": true}

## Cost, from the logged model calls (measured run)
| what | cost | based on |
|---|---|---|
| per CV read | $0.0000 | 52 CVs |
| per CV screened and checked | $0.0011 | 44 CVs |
| **per 100 CVs** | $0.1079 | read + screened + checked |
| per AI interview | $0.0246 | 3 interviews |
| per copilot session | $0.0036 | 2 sessions |

**Fake mode:** no model was called. These are the costs the same tokens would have at the list prices in app/ai/router.py.

### Cost by agent
| agent | calls | cached | tokens | cost | seconds |
|---|---|---|---|---|---|
| interviewer | 83 | 8 | 60239 | $0.0706 | 0.072 |
| screening | 44 | 1 | 24583 | $0.0456 | 0.056 |
| copilot | 38 | 10 | 7816 | $0.0072 | 0.042 |
| requisition | 2 | 0 | 1486 | $0.0044 | 0.004 |
| checker | 3 | 0 | 1049 | $0.0019 | 0.001 |
| diagrams | 3 | 1 | 855 | $0.0017 | 0.0 |
| scorecard | 3 | 0 | 772 | $0.0015 | 0.001 |
| document | 52 | 0 | 31807 | $0.0000 | 0.012 |
| speech | 100 | 0 | 0 | $0.0000 | 12.897 |

### What 1,000 applications a month would cost, from these numbers
CV reading, screening and checking: about **$1.0790**. If 10% are interviewed by the AI: add about **$2.4607** (100 interviews x $0.0246). Add $0.1082 if 30 of them also get a copilot session. These use list prices and a fake-model run; the real number needs a real-model run.

## How fast the interviewer replies
Seconds from the candidate's answer to the next question being playable (50 answers; model calls were fake, so scoring/question/diagram show compute only).
| step | median (s) | slowest (s) |
|---|---|---|
| transcription | 0.0 | 0.0 |
| scoring | 0.0032 | 0.006 |
| question | 0.0016 | 0.0389 |
| diagram | 0.0 | 0.0013 |
| speech | 0.1222 | 0.1487 |
| **whole reply** | 0.1292 | 0.1646 |

Slowest step by median: **speech**. Slowest single answer: candidate 1, question 17 (0.1646 s).

## Copilot warning time
From reports/copilot_eval.json (2026-10-30): average **0.0255 s**, slowest **0.031 s** after a forbidden question ended.

## One improvement, measured before and after
**Reuse the recording of a fixed question instead of speaking it again.** The 8 core questions are the same for every candidate, so the voice only needs to speak them once. Written questions mention the CV, so they are never cached.
|  | seconds of speech for one interview's 8 core questions |
|---|---|
| before (cache off, every candidate) | 1.084 |
| after (cache on, second candidate) | 0.078 |
| after, first candidate (fills the cache) | 1.131 |

Saved **1.006 s per interview (92.8%)**, measured the same way both times with a real voice (operating-system voice (pyttsx3)). The first candidate pays full price once.

## Limits
- Fake mode: model cost is what the tokens would cost at list prices, and model time is only the platform's compute. A real-model run gives real cost and time.
- Speech and transcription times are measured only when a real voice or Whisper ran; fake mode writes a short silent file.
