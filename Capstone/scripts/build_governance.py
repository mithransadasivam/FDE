"""Builds the governance pack in governance/ from the evidence files (Day 4, BR-18).

    python -m scripts.build_governance      (run the evaluations first, or run python -m scripts.quality_gate which does everything)

It writes: classification.md, model_card.md (every number cites an evidence file and is filled FROM that file), risk_register.csv and .md,
candidate_notice.md, explanation_template.md, and evidence/ with a manifest of SHA-256 hashes. scripts/governance_check.py then verifies all of it.
"""
import csv
import hashlib
import json
import shutil
from datetime import date
from pathlib import Path

GOV = Path("governance")
EV = Path("evidence")
REVIEW = "2027-01-31"  # review date for every risk (the next quarterly review)

CLASSIFICATION = """# EU AI Act classification

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
"""

NOTICE = """# Notice to candidates

You are about to talk to an AI interviewer. It will ask you up to 8 questions, some with a diagram. Your answers are recorded and turned into text, and the text is scored by AI against the skills for this role. Only what you say is scored, never your voice, accent or how you speak. A recruiter reviews every interview and makes every decision. Recordings are kept for 6 months and then deleted. If you would rather speak to a person, choose "Ask for a person instead": it will not affect how your application is treated.

## Before a copilot-assisted interview

This interview will be followed by an AI assistant that listens, shows the recruiter a live transcript, suggests questions and ticks the points of a good answer. It never decides: the recruiter asks, scores and decides. The conversation is recorded and kept for 6 months. You can ask for the interview to be held without the assistant.

## When you apply

AI reads your CV and compares your skills with the skills for the job. Your name, contact details, date of birth and address are hidden while AI compares skills. People make every decision. We keep your CV for 180 days and then delete it.
"""

EXPLANATION = """# Why you were not shortlisted (draft: a recruiter reviews this before it is sent)

Dear <first name>,

Thank you for applying for <role>. We compared your CV with the skills for the role. <strengths: where your CV matched, with the words from your CV>

The skills where other applications showed more evidence were: <gaps>.

This comparison was suggested by an AI system and the decision was made by a recruiter, <recruiter>. You can ask for a person to look at your application again.

The platform builds this from the candidate's own scores and quotes (`app/decisions.py: explain_not_shortlisted`) and puts it in the outbox. Nothing is sent until a recruiter approves it.
"""


def ev(name: str) -> dict:
    return json.loads((EV / name).read_text(encoding="utf-8"))


def risks() -> list[dict]:
    acc = ev("bias_accents.json")
    findings = len(acc["findings"])
    rows = [
        ("R-001", "Screening treats candidates differently because of name, gender or age clues", "Measure", "medium", "high", "Trust & quality lead", "Identity hidden before scoring (app/privacy.py); age and gender proxies scrubbed; counterfactual test on 6x5 CV variants", "bias_screening.json"),
        ("R-002", "Interview transcription is less accurate for some voices, lowering their scores", "Measure", "medium", "high", "Voice & interviews lead", f"Accent test with word error rate and score per variant; {findings} finding(s) logged from the simulated run; second scorer; recruiter reviews every scorecard; re-test with real accented speech", "bias_accents.json"),
        ("R-003", "Instructions hidden in a CV, PDF metadata, an email or a spoken answer change a score or an action", "Manage", "high", "high", "Trust & quality lead", "Candidate text is data: scanned, flagged and removed before models read it; evidence check; people approve; 20-attack red team before and after", "red_team.json"),
        ("R-004", "The assistant or a tool leaks private data (contact details, date of birth, salary) or its own instructions", "Manage", "medium", "high", "Agents & platform lead", "Requests refused by code; the tracking database refuses private columns (SQLite authorizer); read-only connection", "red_team.json"),
        ("R-005", "A score cites evidence that does not exist (a fabricated quote)", "Measure", "medium", "high", "Intake & screening lead", "Code checks every quote is in its source; a score without a verified quote becomes 0; the compliance reviewer re-checks and sends work back", "eval_ranking.json"),
        ("R-006", "A decision, message or stage move happens without a person", "Govern", "low", "high", "Agents & platform lead", "supervisor.move() refuses system decisions; approve_and_send refuses non-persons; decision-log completeness check", "red_team.json"),
        ("R-007", "Emotion or voice features (tone, accent, confidence) leak into interview scoring", "Govern", "low", "high", "Voice & interviews lead", "Scoring functions receive transcript text only; a test proves no audio feature is used; no camera", "eval_interview.json"),
        ("R-008", "CVs and recordings are kept longer than allowed or sent to an unapproved model", "Govern", "medium", "medium", "Agents & platform lead", "Retention purge (scripts/purge_expired.py); model router keeps identity-seeing steps on the local model; recordings listed in the model card", "perf.json"),
        ("R-009", "Model accuracy changes when the real model or prompt changes", "Measure", "high", "medium", "Trust & quality lead", "Quality gate in CI re-runs extraction, ranking, interview, copilot, red-team and bias evaluations on every change", "eval_extraction.json"),
        ("R-010", "Candidates are not told AI is involved, or cannot ask for a person", "Govern", "low", "high", "Intake & screening lead", "Notice and consent on the apply page; notice acknowledged before the AI interview and before the copilot; ask-for-a-person flow", "eval_copilot.json"),
        ("R-011", "Numbers measured with fake models are mistaken for real-model performance", "Map", "high", "medium", "Trust & quality lead", "Every report states the mode; the model card repeats it; real-model re-run is listed as an open action", "eval_interview.json"),
        ("R-012", "A real person's CV or voice enters the system", "Map", "low", "high", "Trust & quality lead", "Fictional data only (rule 11); all fixtures are generated; README and CLAUDE.md say so", "eval_extraction.json"),
        ("R-013", "Cost or voice latency grows beyond the targets", "Manage", "medium", "low", "Agents & platform lead", "Cost per 100 CVs and per interview, and voice p95, measured in PERF_REPORT.md; routing and caching", "perf.json"),
        ("R-014", "A model outage stops screening or interviews", "Manage", "medium", "medium", "Agents & platform lead", "Fallback model in the router; /ready reports when a dependency is missing; interview state resumes after a dropped connection", "perf.json"),
    ]
    return [dict(zip(("id", "risk", "nist_function", "likelihood", "impact", "owner", "control", "evidence"), r), review_date=REVIEW) for r in rows]


def model_card() -> str:
    ex, rk, iv, cp = ev("eval_extraction.json"), ev("eval_ranking.json"), ev("eval_interview.json"), ev("eval_copilot.json")
    rt, bs, ba, pf = ev("red_team.json"), ev("bias_screening.json"), ev("bias_accents.json"), ev("perf.json")
    cloud = rk["roles"][0]
    lag = max((f["lag_s"] for f in cp["forbidden_flags"] if "lag_s" in f), default=0)
    return f"""# Model card: AI Hiring Intelligence Platform

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
| CV extraction, fields right on the 12-CV key | {ex['pct']}% [evidence: eval_extraction.json#pct] | at least 90% |
| Shortlist: top-5 overlap with the recruiter's key (Cloud Support Engineer) | {cloud['overlap']} of 5 [evidence: eval_ranking.json#roles.0.overlap] | at least 4 |
| Interview scoring agrees with the key on 30 recorded answers | {iv['scorer_agreement_with_key_pct']}% [evidence: eval_interview.json#scorer_agreement_with_key_pct] | at least 80% |
| Copilot key points agree with the answer key on 4 recordings | {cp['key_point_agreement_pct']}% [evidence: eval_copilot.json#key_point_agreement_pct] | at least 80% |
| Forbidden question flagged (seconds after the question ended) | {lag} s [evidence: eval_copilot.json#forbidden_flags.0.lag_s] | within 3 s |
| Red team: attacks stopped after the guardrails | {rt['stopped_after']} of 20 [evidence: red_team.json#stopped_after] | at least 18 |
| Red team: attacks stopped before the guardrails | {rt['stopped_before']} of 20 [evidence: red_team.json#stopped_before] | (baseline) |
| Bias, screening: unexplained score differences across {bs['variants']} CV versions | {bs['unexplained_differences']} [evidence: bias_screening.json#unexplained_differences] | 0 |
| Bias, screening: adverse impact ratio | {bs['adverse_impact_ratio']} [evidence: bias_screening.json#adverse_impact_ratio] | at least 0.8 |
| Cost per 100 CVs screened (at list prices, after routing) | ${pf['cost']['per_100_cvs_after']} [evidence: perf.json#cost.per_100_cvs_after] | reported |
| Cost per AI interview (assumed speech prices) | ${pf['cost']['per_ai_interview_total']} [evidence: perf.json#cost.per_ai_interview_total] | reported |
| Voice: estimated p95 from candidate finishing to next question starting | {pf['voice']['p95_estimated_s']} s [evidence: perf.json#voice.p95_estimated_s] | within 2.5 s |

## Known limitations
- The figures use fake models. The recorded answers were built from the question bank, so interview agreement is expected to be high; real answers will be harder.
- The four "accents" are four speaking styles from a text-to-speech engine, not real accents (`BIAS_REPORT.md`). {len(ba['findings'])} difference(s) above half a point were found in the simulated run [evidence: bias_accents.json#findings].
- Injection detection uses text rules. A paraphrased instruction is not caught by them; the evidence check and the recruiter's review are the backstops (`SECURITY_FINDINGS.md`).
- The recruiter's key is a fictional rule, so overlap with it shows consistency with one stated standard, not with human hiring outcomes.

## Human oversight
A person approves the rubric, the shortlist, every move to a later stage, every email, and every final decision. `app/supervisor.py` refuses a decision made by the system. The recruiter reviews every interview scorecard and can override any score. Candidates can ask for a person at any time.

## Recordings and retention
Voice notes, CVs and interview recordings are **personal data**. CVs are kept for 180 days and interview recordings for 6 months, then deleted (`scripts/purge_expired.py`). Recordings are never used to train anything and are sent only to models listed in `.env` (the approved list). Recordings listed here: requisition voice notes, AI-interview answers, recorded human interviews.

## Risks
See `risk_register.csv`.
"""


def risk_markdown(rows: list[dict]) -> str:
    L = ["# Risk register", "", "NIST AI RMF functions: Govern, Map, Measure, Manage. Review date for every risk: " + REVIEW + ".", "",
         "| Id | Risk | Function | Likelihood | Impact | Owner | Control | Evidence |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['id']} | {r['risk']} | {r['nist_function']} | {r['likelihood']} | {r['impact']} | {r['owner']} | {r['control']} | `{r['evidence']}` |")
    return "\n".join(L) + "\n"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    GOV.mkdir(exist_ok=True)
    (GOV / "evidence").mkdir(exist_ok=True)
    # the evidence folder: every evidence file and report, with a manifest of hashes
    manifest = {"generated": date.today().isoformat(), "files": {}}
    for src in sorted(EV.glob("*.json")) + [Path(n) for n in ("EVAL_REPORT.md", "PERF_REPORT.md", "SECURITY_FINDINGS.md", "BIAS_REPORT.md") if Path(n).exists()]:
        dest = GOV / "evidence" / src.name
        shutil.copyfile(src, dest)
        manifest["files"][src.name] = sha256(dest)
    rows = risks()
    (GOV / "classification.md").write_text(CLASSIFICATION, encoding="utf-8")
    (GOV / "model_card.md").write_text(model_card(), encoding="utf-8")
    with (GOV / "risk_register.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (GOV / "risk_register.md").write_text(risk_markdown(rows), encoding="utf-8")
    (GOV / "candidate_notice.md").write_text(NOTICE, encoding="utf-8")
    (GOV / "explanation_template.md").write_text(EXPLANATION, encoding="utf-8")
    (GOV / "evidence" / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"Governance pack written to governance/ ({len(rows)} risks, {len(manifest['files'])} evidence files hashed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
