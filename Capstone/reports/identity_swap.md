# Identity swap test

**Result: PASS**  
Date: 2026-10-30T01:16:56+00:00  
Run: fake models (simulated); models: openrouter/anthropic/claude-haiku-4.5  
Settings: {"candidates": 10, "max_total_change": 2.0, "planner": "app.interview.bank.build_plan", "run": "fake models (simulated)"}

## Pass rule
No screening total may change by more than 2 points out of 100, and no planned must-have may be dropped. Largest change in total: **0.0**; planned must-haves dropped: **0**.

## By kind of change
| kind | variants | largest change (blinded) | largest change (blinding OFF) | skill scores changed | plans changed |
|---|---|---|---|---|---|
| name | 50 | 0.0 | 0.0 | 0 | 0 |
| pronoun | 60 | 0.0 | 0.0 | 0 | 0 |
| age | 40 | 0.0 | 0.0 | 0 | 0 |
| other | 60 | 0.0 | 0.0 | 0 | 0 |

The 'blinding OFF' column is the comparison: the same variants scored from the raw profile. The difference shows what blinding protects against.

## By candidate
| candidate | largest change in total | (blinding off) | variants with a changed skill | variants with a changed plan |
|---|---|---|---|---|
| 1 | 0.0 | 0.0 | 0 | 0 |
| 2 | 0.0 | 0.0 | 0 | 0 |
| 4 | 0.0 | 0.0 | 0 | 0 |
| 11 | 0.0 | 0.0 | 0 | 0 |
| 18 | 0.0 | 0.0 | 0 | 0 |
| 27 | 0.0 | 0.0 | 0 | 0 |
| 49 | 0.0 | 0.0 | 0 | 0 |
| 20 | 0.0 | 0.0 | 0 | 0 |
| 39 | 0.0 | 0.0 | 0 | 0 |
| 45 | 0.0 | 0.0 | 0 | 0 |

## Findings: identity clues that survived into the blind text
- none reached the blind text

## Limits
- In fake mode extraction and scoring are rule-based, so this proves the pipeline's structure (what reaches scoring), not a language model's behaviour. Run it once with real models.
- Only the clues listed above were tested; proxies we did not think of are not covered.
