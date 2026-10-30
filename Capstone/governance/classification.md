# EU AI Act classification

> A teaching summary, **not legal advice**. Check the dates and the current text before you rely on them. Under the Digital Omnibus on AI proposal the
> high-risk obligations for Annex III systems are expected to apply from **2 December 2027**; confirm this against the final text.

## Classification: HIGH RISK (Annex III, point 4)

The AI Hiring Intelligence Platform is used for the **recruitment and selection of natural persons**: to filter and evaluate applications and to evaluate
candidates in interviews. That is a high-risk use under **Annex III, point 4(a)**. A person who decides with the platform's help does not change the
classification, because the system still influences the decision.

## Prohibited practices: avoided

| Practice | Article | How the platform avoids it |
|---|---|---|
| Emotion recognition in the workplace (including recruitment) | Art. 5(1)(f) | Interviews are scored only on the words said. No camera. No tone, emotion, confidence, accent or fluency is inferred. A test shows the scoring functions receive text only (`tests/test_governance.py`). |
| Biometric categorisation of protected traits | Art. 5(1)(g) | No biometric data is processed. |


## Proof that the platform does no emotion recognition (Article 5(1)(f)): read from the code and settings, not asserted

- **Settings.** The platform's settings (`app/config.py::Settings`) have 32 fields: `database_url`, `ops_database_url`, `storage_dir`, `retention_days`, `speech_cache`, `secret_key`, `fake_models`, `llm_model`, `vision_model`, `openrouter_api_key`, `whisper_model`, `tesseract_cmd`, `review_threshold`, `fake_transcripts_dir`, and more. Fields about a camera, video, emotion, face, sentiment, biometrics or tone: **none**.
- **Code.** 120 files (`app/**/*.py`, `templates/**/*.html`, `static/*.js`) were scanned for emotion, face, voice-analysis and camera code: **0 match(es)**.

- **What scoring receives.** `app/agents/interviewer.py::score_text(q: dict, transcript: str, hint_used: bool = False, candidate_id: int | None = None) -> app.schemas_ext.AnswerScore`: a question, the words said, whether a hint was used and an id. Not audio, not a recording, not a picture. (Test: `tests/test_governance.py::test_scoring_functions_take_text_only`.)
- **Camera.** The interview page asks only for the microphone (`getUserMedia({audio: true})`). No video is requested or stored.

## Transparency to candidates (Article 50, Article 26(7))

The notice a candidate must read and acknowledge before the AI interview (`app/web/interview.py::NOTICE`, the same words the page shows):

> You are about to talk to an AI interviewer. The interview takes about 25 minutes and you answer by voice. The questions follow on from your answers, and some come with a diagram. Your answers are turned into text, and the text is scored by AI against the skills for this role. Only what you say is scored, never your voice, accent or how you speak. The interview is recorded (the questions and your answers) so the hiring team can review it: the hiring manager and the recruiters for this job can listen to it, and the recording is deleted after 6 months. A recruiter reviews every interview and makes every decision. If you would rather speak to a person, choose "Ask for a person instead": it will not affect how your application is treated.

Screenshot: `docs\screenshots\15-apply-with-ai-notice.png`.

## Obligations that follow, and where the platform meets them

| Obligation | Article | Evidence in this repository |
|---|---|---|
| Risk management system | Art. 9 | `risk_register.csv` (18 risks, NIST AI RMF functions, owners, controls, evidence, review dates) |
| Data and data governance | Art. 10 | Fictional data only; identity hidden while scoring (`app/privacy.py`); bias tests on screening and on transcription (`BIAS_REPORT.md`) |
| Technical documentation | Art. 11 | `model_card.md`, `README.md`, this folder |
| Record-keeping (logs) | Art. 12 | The decision log, traces per agent (Phoenix / `agent_traces`), the model-call ledger, and the hashed evidence folder |
| Transparency to deployers | Art. 13 | The model card; the recruiter sees every score's evidence on the scorecard |
| Human oversight | Art. 14 | Approval gates at every decision (`app/supervisor.py`); the recruiter can override any score; the candidate can ask for a person |
| Accuracy, robustness, cybersecurity | Art. 15 | The quality bar (`EVAL_REPORT.md`), the red team (`SECURITY_FINDINGS.md`), the fallback model |
| Duty to inform people | Art. 26(7), Art. 50 | The candidate notice before the AI interview and before a copilot-assisted interview (`candidate_notice.md`) |
| Right to an explanation | Art. 86 | The "why was I not shortlisted" explanation, reviewed by a recruiter before it is sent (`explanation_template.md`) |

## What the deployer (the company) must still do

Complete a conformity assessment and register the system before the obligations apply; assign trained human overseers; carry out a data protection
impact assessment under the GDPR; keep the logs for the required period; and monitor the system after deployment. This pack shows how the platform
supports those duties; it does not replace them.
