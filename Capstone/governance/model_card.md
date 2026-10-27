# Model card: AI Hiring Intelligence Platform

Every number below is followed by `[evidence: file#path]`. `scripts/governance_check.py` checks each one against the file and checks the file's hash in `governance/evidence/manifest.json`.

## Intended use
Help a company's recruiters and hiring managers screen applications, run a first-round AI interview and assist a recruiter in the second round, **fairly, with evidence, and under a person's control**. Used for recruitment, which is **high risk** (EU AI Act Annex III point 4): see `classification.md`.

## Out of scope
Making offers, salary decisions, background checks, video or face analysis, emotion recognition, training or fine-tuning on candidates' data, and use with real candidates' data without the deployer's own conformity assessment.

## Models and data
- Agents (8) plus a supervisor, each with its own tools (least privilege). Models are reached only through `app/ai/llm.py` and `app/ai/voice.py`.
- Model router: small model for extraction and point-ticking, large model for scoring and suggestions, local model for any step that sees identity.
- Mode of the figures below: **fake models** (rule-based stand-ins) with real recorded and synthesised audio and real OCR. Re-run with `FAKE_MODELS=0` before relying on any figure for a real model.
- Data: **fictional only**: 52 CVs for REQ-014 plus 40 more for two other roles, 30 bias-test variants, 30 recorded interview answers, 4 recorded interviews, 20 voice-variant clips, all generated for this project.

## Evaluation results
| What | Result | Target |
|---|---|---|
| CV extraction, fields right on the 12-CV key | 100.0% [evidence: eval_extraction.json#pct] | at least 90% |
| Shortlist: top-5 overlap with the recruiter's key (Cloud Support Engineer) | 5 of 5 [evidence: eval_ranking.json#roles.0.overlap] | at least 4 |
| Interview scoring agrees with the key on 30 recorded answers | 100.0% [evidence: eval_interview.json#scorer_agreement_with_key_pct] | at least 80% |
| Copilot key points agree with the answer key on 4 recordings | 100.0% [evidence: eval_copilot.json#key_point_agreement_pct] | at least 80% |
| Forbidden question flagged (seconds after the question ended) | 0.0009 s [evidence: eval_copilot.json#forbidden_flags.0.lag_s] | within 3 s |
| Red team: attacks stopped after the guardrails | 20 of 20 [evidence: red_team.json#stopped_after] | at least 18 |
| Red team: attacks stopped before the guardrails | 5 of 20 [evidence: red_team.json#stopped_before] | (baseline) |
| Bias, screening: unexplained score differences across 30 CV versions | 0 [evidence: bias_screening.json#unexplained_differences] | 0 |
| Bias, screening: adverse impact ratio | 1.0 [evidence: bias_screening.json#adverse_impact_ratio] | at least 0.8 |
| Cost per 100 CVs screened (at list prices, after routing) | $0.1015 [evidence: perf.json#cost.per_100_cvs_after] | reported |
| Cost per AI interview (assumed speech prices) | $0.04063 [evidence: perf.json#cost.per_ai_interview_total] | reported |
| Voice: estimated p95 from candidate finishing to next question starting | 2.15 s [evidence: perf.json#voice.p95_estimated_s] | within 2.5 s |

## Known limitations
- The figures use fake models. The recorded answers were built from the question bank, so interview agreement is expected to be high; real answers will be harder.
- The four "accents" are four speaking styles from a text-to-speech engine, not real accents (`BIAS_REPORT.md`). 1 difference(s) above half a point were found in the simulated run [evidence: bias_accents.json#findings].
- Injection detection uses text rules. A paraphrased instruction is not caught by them; the evidence check and the recruiter's review are the backstops (`SECURITY_FINDINGS.md`).
- The recruiter's key is a fictional rule, so overlap with it shows consistency with one stated standard, not with human hiring outcomes.

## Human oversight
A person approves the rubric, the shortlist, every move to a later stage, every email, and every final decision. `app/supervisor.py` refuses a decision made by the system. The recruiter reviews every interview scorecard and can override any score. Candidates can ask for a person at any time.

## Recordings and retention
Voice notes, CVs and interview recordings are **personal data**. CVs are kept for 180 days and interview recordings for 6 months, then deleted (`scripts/purge_expired.py`). Recordings are never used to train anything and are sent only to models listed in `.env` (the approved list). Recordings listed here: requisition voice notes, AI-interview answers, recorded human interviews.

## Risks
See `risk_register.csv`.
