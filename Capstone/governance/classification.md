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

## Obligations that follow, and where the platform meets them

| Obligation | Article | Evidence in this repository |
|---|---|---|
| Risk management system | Art. 9 | `risk_register.csv` (14 risks, NIST AI RMF functions, owners, controls, evidence, review dates) |
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
