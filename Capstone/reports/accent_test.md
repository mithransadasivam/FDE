# Accent test

**Result: PASS**  
Date: 2026-10-30T01:37:39+00:00  
Run: fake models (simulated); models: openrouter/anthropic/claude-haiku-4.5  
Settings: {"answers": 6, "voices": ["British English (alan)", "Scottish English (alba)", "Irish-influenced English (jenny_dioco)", "US English (lessac)", "US English (ryan)", "US English, slow (lessac x1.5)", "US English, fast (lessac x0.65)"], "max_level_difference": 1, "whisper_model": "base.en", "scoring": "fake (rule-based)", "quick": false}

## Pass rule
No answer's level may differ by more than 1 between voices. Largest difference: **0**.

## Word error rate by voice (mean over the answers)
| voice | mean WER |
|---|---|
| British English (alan) | 1.9% |
| Scottish English (alba) | 4.9% |
| Irish-influenced English (jenny_dioco) | 2.7% |
| US English (lessac) | 2.2% |
| US English (ryan) | 6.3% |
| US English, slow (lessac x1.5) | 4.5% |
| US English, fast (lessac x0.65) | 8.1% |

Highest mean error rate: **US English, fast (lessac x0.65)** (8.1%). Highest single recording: `reports\accent_audio\answer6_partial_fast_en_US-lessac-medium.wav` (30.8%).

## Level per voice, for each answer
| answer | kind | skill | level from the text | British English (alan) | Scottish English (alba) | Irish-influenced English (jenny_dioco) | US English (lessac) | US English (ryan) | US English, slow (lessac x1.5) | US English, fast (lessac x0.65) | largest difference |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | strong | Cloud networking | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 0 |
| 2 | strong | Incident handling | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 0 |
| 3 | weak | Linux troubleshooting | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 4 | weak | Customer communication | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 5 | partial | Resilience | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 0 |
| 6 | partial | Incident handling | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 0 |

## The answers
1. **strong**, T-04 (sample interview 3): First I check the route table of the subnet. Then outbound security group and network ACL rules. A private subnet needs a NAT gateway for outbound internet acce...
2. **strong**, T-06 (sample interview 3): I acknowledge the alert and assess who is affected and how badly. I communicate early and open an incident channel for stakeholders. I mitigate first, for examp...
3. **weak**, T-01 (sample interview 5): I would probably restart it and hope it helps....
4. **weak**, T-10 (sample interview 5): I would just check the logs....
5. **partial**, T-03 (sample interview 3, cut to its first 1 sentence(s)): While the primary is down, orders fail or have to be queued....
6. **partial**, T-07 (sample interview 3, cut to its first 1 sentence(s)): I look at what runs at 2am: cron jobs, backups or batch jobs....

## Limits
- These are computer voices. They do not represent real people's accents well: passing this test does not prove there is no problem with real speakers.
- Scoring ran in fake (rule-based keyword) mode: with the rule-based scorer a mis-heard keyword can lower a level, which is what this test would show; a language model may be more or less forgiving. Run it again with real models.
- Only a few answers and voices were used.
