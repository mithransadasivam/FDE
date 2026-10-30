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


---
# Part 2: read from the settings, the code and the reports (generated 2026-10-30)

## Every agent, with its model, its inputs and outputs, and what it must never do
Models configured in `app/config.py`: large `openrouter/anthropic/claude-haiku-4.5`, small `openrouter/google/gemini-2.5-flash-lite`, local `ollama/llama3.1`, fallback `openrouter/openai/gpt-4o-mini`, vision `openrouter/google/gemini-2.5-flash-lite`, speech to text `faster-whisper base.en`. Mode when this was built: **fake models**.

| Agent | Models actually called (from the model-call log) | Tools it may call (the only inputs and outputs it has) | Step limit |
|---|---|---|---|
| supervisor | no model call logged yet | `checkpoint`, `decision_log`, `routing_rule` | 50 |
| requisition | openrouter/anthropic/claude-haiku-4.5 (large, for judgement) | `save_rubric`, `transcribe`, `wording_check` | 10 |
| document | ollama/llama3.1 (local, for identity) | `find_duplicate`, `read_docx`, `read_image`, `read_pdf` | 10 |
| screening | openrouter/anthropic/claude-haiku-4.5 (large, for scoring) | `score_item`, `search_cvs` | 40 |
| interviewer | openrouter/anthropic/claude-haiku-4.5 (large, for judgement)<br>openrouter/anthropic/claude-haiku-4.5 (large, for scoring) | `end_interview`, `give_hint`, `listen`, `score_answer`, `show_diagram`, `speak` | 60 |
| copilot | openrouter/anthropic/claude-haiku-4.5 (large, for suggestion)<br>openrouter/google/gemini-2.5-flash-lite (small, for point_ticking) | `coverage`, `flag_cv_conflict`, `mark_point`, `suggest_question`, `transcribe_stream` | 400 |
| assistant | openrouter/anthropic/claude-haiku-4.5 (large, for chat) | `get_candidate`, `list_requisitions`, `search_candidates`, `search_cvs`, `search_policy` | 12 |
| communications | ollama/llama3.1 (local, for identity) | `draft_email`, `find_slot` | 10 |
| compliance | no model call logged yet | `check_evidence`, `check_log`, `scan_prompt_log` | 80 |

- **supervisor**: inputs and outputs are its tools: . It must never: call any of the other 29 tools (refused by code in `app/agents/base.py`).
- **requisition**: inputs and outputs are its tools: `save_rubric` (Save the generated job description and rubric as a draft (the hiring manager approves it)); `transcribe` (Turn the hiring manager's voice note into text); `wording_check` (Flag biased wording with a reason and a neutral rewrite). It must never: call any of the other 26 tools (refused by code in `app/agents/base.py`).
- **document**: inputs and outputs are its tools: `find_duplicate` (Find other applications with the same e-mail or phone number); `read_docx` (Read the text of a Word CV); `read_image` (Read a scanned CV or a profile screenshot (vision model, or OCR in fake mode)); `read_pdf` (Read the text of a PDF CV). It must never: call any of the other 25 tools (refused by code in `app/agents/base.py`).
- **screening**: inputs and outputs are its tools: `score_item` (Score one rubric skill for one candidate (used to re-score after a recruiter override or a send-back)); `search_cvs` (Hybrid keyword + vector search over the blind sections of the CV pool). It must never: call any of the other 27 tools (refused by code in `app/agents/base.py`).
- **interviewer**: inputs and outputs are its tools: `end_interview` (End the interview and build the scorecard); `give_hint` (Give the hint for a question (recorded on the scorecard, and it lowers the best score)); `listen` (Record and transcribe the candidate's answer); `score_answer` (Score an answer against the guide with a quote from the transcript); `show_diagram` (Show an architecture diagram with the question); `speak` (Say a question aloud (the page speaks it in the browser)). It must never: call any of the other 23 tools (refused by code in `app/agents/base.py`).
- **copilot**: inputs and outputs are its tools: `coverage` (Which rubric skills have been covered so far); `flag_cv_conflict` (Compare what the candidate says with the CV and word any conflict as something to clarify); `mark_point` (Tick the key points of a good answer that the candidate has now said); `suggest_question` (Suggest 2-3 questions for the recruiter to consider); `transcribe_stream` (Return a speaker-labelled transcript line (recruiter: left channel, candidate: right channel)). It must never: call any of the other 24 tools (refused by code in `app/agents/base.py`).
- **assistant**: inputs and outputs are its tools: `get_candidate` (Tracking system: one candidate's public fields (private columns are refused)); `list_requisitions` (Tracking system: list the requisitions (read-only)); `search_candidates` (Tracking system: search candidates by skill, stage or years (public fields only)); `search_cvs` (Hybrid keyword + vector search over the blind sections of the CV pool); `search_policy` (Search the hiring policy). It must never: call any of the other 24 tools (refused by code in `app/agents/base.py`).
- **communications**: inputs and outputs are its tools: `draft_email` (Draft an email to a candidate into the approval queue. Never sends); `find_slot` (Find free interview slots in the fictional calendar). It must never: call any of the other 27 tools (refused by code in `app/agents/base.py`).
- **compliance**: inputs and outputs are its tools: `check_evidence` (Check that every score has a quote that really is in its source); `check_log` (Check the decision log is complete: every decision has a person, a reason and a matching record); `scan_prompt_log` (Scan the prompt log for identity details or protected traits in scoring prompts). It must never: call any of the other 26 tools (refused by code in `app/agents/base.py`).

## Known limits, taken from the reports
**Identity swap test** (`reports/identity_swap.md`):
- In fake mode extraction and scoring are rule-based, so this proves the pipeline's structure (what reaches scoring), not a language model's behaviour. Run it once with real models.
- Only the clues listed above were tested; proxies we did not think of are not covered.
**Accent test** (`reports/accent_test.md`):
- These are computer voices. They do not represent real people's accents well: passing this test does not prove there is no problem with real speakers.
- Scoring ran in fake (rule-based keyword) mode: with the rule-based scorer a mis-heard keyword can lower a level, which is what this test would show; a language model may be more or less forgiving. Run it again with real models.
- Only a few answers and voices were used.
**Copilot evaluation** (`reports/copilot_eval.md`):
- The practice interviews are scripted and fictional: the copilot is tested on moments we planned, in clean text. Real, unplanned interviews will be harder (accents, overlap, speech-to-text errors); test those with a person scoring the copilot's cards.
- Ran in fake mode (rule-based) at 4x. A missed moment can mean the key words did not match, not that it was missed by a person.
**Cost and speed** (`reports/cost_and_speed.md`):
- Fake mode: model cost is what the tokens would cost at list prices, and model time is only the platform's compute. A real-model run gives real cost and time.
- Speech and transcription times are measured only when a real voice or Whisper ran; fake mode writes a short silent file.
**The whole journey** (`reports/journey.md`):
- Fake mode: the AI parts are rule-based stand-ins, so this proves the platform works end to end, not how good a real model is. Run with `--real` for that.
- The AI interviews use recorded answers from the starter kit ('strong' and 'weak' simulated candidates).


## The human oversight points
Every point where a person decides is listed, from the supervisor's table, in `oversight.md`.
