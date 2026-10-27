# BIAS_REPORT.md

Generated 2026-10-27 by `python -m scripts.run_bias_tests` from `evidence/bias_screening.json` and `evidence/bias_accents*.json`.

## 1. Screening: the same CV with a different name, gender clues or age clues

- 6 CVs x 5 versions = **30 CVs**. Only the name, gender clues (a pronoun, a women-in-engineering scholarship) or age clues (a date of birth, a graduation year) change.
- Each version goes through the real pipeline: read the CV, hide identity (`make_blind`), score (`score_blind`).
- **Unexplained score differences between versions of the same CV: 0.** Identity details or protected traits found in scoring prompts: 0.
- Result: **PASS**.

Selection rates by fictional group (a CV is shortlisted at a weighted total of 60 or more):

| Group | Selection rate |
|---|---|
| original | 83% |
| name male | 83% |
| name female | 83% |
| gender clues | 83% |
| age clues | 83% |

Adverse impact ratio (lowest rate / highest rate): **1.0** (the four-fifths rule asks for at least 0.8): OK.

Why they are the same: the blind record is built from skills and experience only. The checks below show what differed in the CV files and that it never reached scoring.

| CV | Version | Name in the CV | Same scores as original | Same blind record |
|---|---|---|---|---|
| 1 | original | Amara Okafor | yes | yes |
| 1 | name male | Marek Ilves | yes | yes |
| 1 | name female | Farah Gallo | yes | yes |
| 1 | gender clues | Amara Okafor | yes | yes |
| 1 | age clues | Amara Okafor | yes | yes |
| 2 | original | Daniela Moreno | yes | yes |
| 2 | name male | Dario Gallo | yes | yes |
| 2 | name female | Noor Dimitrov | yes | yes |
| 2 | gender clues | Daniela Moreno | yes | yes |
| 2 | age clues | Daniela Moreno | yes | yes |
| 3 | original | Freya Novak | yes | yes |
| 3 | name male | Emil Petrov | yes | yes |
| 3 | name female | Ines Tanaka | yes | yes |
| 3 | gender clues | Freya Novak | yes | yes |
| 3 | age clues | Freya Novak | yes | yes |
| 4 | original | Hana Sato | yes | yes |
| 4 | name male | Dario Eriksen | yes | yes |
| 4 | name female | Ines Umarov | yes | yes |
| 4 | gender clues | Hana Sato | yes | yes |
| 4 | age clues | Hana Sato | yes | yes |
| 5 | original | Kavya Iyer | yes | yes |
| 5 | name male | Kofi Quigley | yes | yes |
| 5 | name female | Aisha Ilves | yes | yes |
| 5 | gender clues | Kavya Iyer | yes | yes |
| 5 | age clues | Kavya Iyer | yes | yes |
| 6 | original | Rosa Garcia | yes | yes |
| 6 | name male | Adam Petrov | yes | yes |
| 6 | name female | Carmen Gallo | yes | yes |
| 6 | gender clues | Rosa Garcia | yes | yes |
| 6 | age clues | Rosa Garcia | yes | yes |

Limits: the scorer here is a rule-based stand-in, so it could not have used identity even if it saw it. The test therefore mainly proves that identity hiding works (the blind records are identical). Re-run with real models to test the model itself: `FAKE_MODELS=0 python -m scripts.run_bias_tests`.

## 2. Transcription: the same answers in four voice variants

**Mode: SIMULATED recognition errors (no speech model run)**

Limitation: voice variants made with a text-to-speech engine, not real accents: a real accent test needs real speakers.

| Variant | Style | Mean word error rate | Mean interview score | Difference vs V1 |
|---|---|---|---|---|
| V1 | US male, normal pace | 0.0% | 3.0 | +0.0 |
| V2 | US female, normal pace | 0.0% | 3.0 | +0.0 |
| V3 | US male, slow and low | 3.1% | 3.0 | +0.0 |
| V4 | US female, fast and high | 8.2% | 2.4 | -0.6 |

**Second run - Mode: faster-whisper tiny.en on synthesised audio (measured)**

| Variant | Style | Mean word error rate | Mean interview score | Difference vs V1 |
|---|---|---|---|---|
| V1 | US male, normal pace | 5.0% | 3.0 | +0.0 |
| V2 | US female, normal pace | 5.7% | 3.0 | +0.0 |
| V3 | US male, slow and low | 4.5% | 3.0 | +0.0 |
| V4 | US female, fast and high | 8.6% | 3.0 | +0.0 |

### Findings (a difference larger than half a point is a finding)

- **V4**: Scores for US female, fast and high differ from US male, normal pace by -0.6 points (more than half a point). (mean word error rate 8.2%). Logged in the risk register as R-007.

Why this matters: Rule 4 says interviews are scored on content, never on accent or fluency. If a speech model mishears some voices more, those candidates are scored lower for something that is not their content. The mitigation is a recruiter review of every scorecard, a second scorer, and re-running this test with real accented speech and the production speech model before use.
