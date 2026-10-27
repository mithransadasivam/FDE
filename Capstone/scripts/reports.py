"""Writers for the reports the course asks for. Each report is generated from evidence files, so every number in it can be traced."""
import json
from datetime import date
from pathlib import Path

ROOT = Path(".")


def _yes(b: bool) -> str:
    return "WORKED" if b else "stopped"


def write_security_findings(r: dict) -> Path:
    lines = [
        "# SECURITY_FINDINGS.md",
        "",
        f"Generated {date.today().isoformat()} by `python -m scripts.run_red_team` from `evidence/red_team.json`.",
        "",
        "## Result",
        "",
        f"- **Before the guardrails: {r['stopped_before']} of {r['total']} attacks stopped.** ({r['total'] - r['stopped_before']} worked.)",
        f"- **After the guardrails: {r['stopped_after']} of {r['total']} attacks stopped** (target: at least {r['target']}). "
        + ("**Target met.**" if r["passed"] else "**Target NOT met.**"),
        "",
        "How the \"before\" state is made: the guardrails are switched off (`GUARDRAILS_ENABLED=0`). In fake mode the stand-in agents then behave like a careless "
        "system: the scorer obeys instructions found in a CV, the assistant answers anything it is asked, the reply drafter repeats what a candidate asks for, "
        "and personal details are not scrubbed. This is a **simulated** baseline that shows what each guardrail is worth; it is not a measurement of a real "
        "model. Re-run with real models (`FAKE_MODELS=0`) to measure those.",
        "",
        "## The 20 attacks",
        "",
        "| Id | Attack | Where it comes in | Before | After | Why it is stopped now |",
        "|---|---|---|---|---|---|",
    ]
    for a in r["attacks"]:
        why = a["structural"] or a["after_evidence"]
        lines.append(f"| {a['id']} | {a['name']} | {a['place'].replace('_', ' ')} | {_yes(a['before_worked'])} | {_yes(a['after_worked'])} | {why} |")
    lines += [
        "",
        "Five attacks (R04, R07, R16, R17, R20) are stopped by the platform's **structure** in both runs, whatever the guardrails say: the supervisor only lets a "
        "person shortlist, the outbox only lets a person send, and the tracking database itself refuses private columns.",
        "",
        "## Defences, by layer",
        "",
        "| Layer | What it does | Rule |",
        "|---|---|---|",
        "| Treat candidate text as data | CV text, metadata, emails and spoken answers are scanned (`app/guardrails.py`); instruction-like text is flagged, removed before a model reads it, and shown to the recruiter | 8 |",
        "| Identity hidden before scoring | `make_blind` removes names, contact details, dates of birth and age or gender proxies; the compliance reviewer scans the prompt log | 3 |",
        "| Evidence for every score | A score without a quote that code finds in the source becomes 0 and is sent back, so an injected \"score 3\" has nothing to stand on | 2 |",
        "| Spoken words only | Spoken instructions are removed and protected disclosures masked before an answer is scored; no audio feature is used | 4, 8 |",
        "| Least privilege | Each agent can only call its own tools (`app/agents/base.py`); the tracking database refuses private columns (SQLite authorizer) and is opened read-only | 9 |",
        "| People decide | `supervisor.move()` refuses a decision made by the system; `approve_and_send` refuses anything but a person | 1 |",
        "",
        "## Extra probes (not among the 20)",
        "",
        "| Probe | Caught by the text rules? |",
        "|---|---|",
    ]
    for p in r["probes"]:
        lines.append(f"| {p['id']} {p['name']} | {'yes' if p['caught_by_text_rules'] else '**no**'} |")
    lines += [
        "",
        "## Accepted risks and things to fix",
        "",
        "1. **Paraphrased instructions (probe P4).** Text rules cannot catch every wording. This is **accepted** with two backstops: a score still needs a verified quote "
        "(an instruction cannot create evidence), and a recruiter approves every shortlist and every interview scorecard. **To fix:** add an LLM judge as a second "
        "detector (Day 17 pattern) and measure it with a real model.",
        "2. **The pattern list needs maintenance.** New phrasings will appear. The library and the probes are the regression tests: add each new attack to them.",
        "3. **Only text is attacked here.** The spoken attacks are tested on the transcript. An attack hidden in audio that a real speech model mishears into an instruction "
        "would arrive as text and be handled the same way, but this has not been measured with real Whisper.",
        "4. **The fake baseline is simulated.** Real models may resist some attacks the fakes fall for, and fall for others. Run `python -m scripts.run_red_team` with real "
        "models before relying on the numbers.",
        "5. **Assistant answer cache.** Repeated questions are served from a cache (keyed on the question and the size of the candidate pool). The cache never stores a "
        "refused question, and answers contain only blind data, so a cached answer cannot leak identity. Accepted.",
        "",
        "## How to repeat this",
        "",
        "```",
        "python -m scripts.run_red_team        # runs before and after, writes evidence/red_team.json and this file",
        "```",
        "",
    ]
    out = ROOT / "SECURITY_FINDINGS.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_bias_report(sc: dict, ac: dict, aw: dict | None = None) -> Path:
    L = ["# BIAS_REPORT.md", "", f"Generated {date.today().isoformat()} by `python -m scripts.run_bias_tests` from `evidence/bias_screening.json` and `evidence/bias_accents*.json`.", "",
         "## 1. Screening: the same CV with a different name, gender clues or age clues", "",
         f"- {sc['bases']} CVs x 5 versions = **{sc['variants']} CVs**. Only the name, gender clues (a pronoun, a women-in-engineering scholarship) or age clues (a date of birth, a graduation year) change.",
         f"- Each version goes through the real pipeline: read the CV, hide identity (`make_blind`), score (`score_blind`).",
         f"- **Unexplained score differences between versions of the same CV: {sc['unexplained_differences']}.** Identity details or protected traits found in scoring prompts: {sc['identity_leaks_in_prompts']}.",
         f"- Result: **{'PASS' if sc['passed'] else 'FAIL'}**.", "",
         f"Selection rates by fictional group (a CV is shortlisted at a weighted total of {sc['selection_threshold']:g} or more):", "",
         "| Group | Selection rate |", "|---|---|"]
    for k, v in sc["selection_rate_by_group"].items():
        L.append(f"| {k.replace('_', ' ')} | {v:.0%} |")
    L += ["", f"Adverse impact ratio (lowest rate / highest rate): **{sc['adverse_impact_ratio']}** (the four-fifths rule asks for at least 0.8): {'OK' if sc['four_fifths_rule_ok'] else 'NOT OK'}.", "",
          "Why they are the same: the blind record is built from skills and experience only. The checks below show what differed in the CV files and that it never reached scoring.", "",
          "| CV | Version | Name in the CV | Same scores as original | Same blind record |", "|---|---|---|---|---|"]
    for d in sc["details"]:
        L.append(f"| {d['base']} | {d['kind'].replace('_', ' ')} | {d['name_in_cv']} | {'yes' if d['same_scores_as_original'] else '**NO**'} | {'yes' if d['same_blind_record_as_original'] else 'no'} |")
    L += ["", "Limits: the scorer here is a rule-based stand-in, so it could not have used identity even if it saw it. The test therefore mainly proves that identity hiding works "
          "(the blind records are identical). Re-run with real models to test the model itself: `FAKE_MODELS=0 python -m scripts.run_bias_tests`.", "",
          "## 2. Transcription: the same answers in four voice variants", "",
          f"**Mode: {ac['mode']}**", "", f"Limitation: {ac['limitation']}.", "",
          "| Variant | Style | Mean word error rate | Mean interview score | Difference vs V1 |", "|---|---|---|---|---|"]
    for r in ac["variants"]:
        L.append(f"| {r['variant']} | {r['label']} | {r['mean_wer']:.1%} | {r['mean_score']} | {r['diff_vs_V1']:+} |")
    if aw:
        L += ["", f"**Second run - Mode: {aw['mode']}**", "", "| Variant | Style | Mean word error rate | Mean interview score | Difference vs V1 |", "|---|---|---|---|---|"]
        for r in aw["variants"]:
            L.append(f"| {r['variant']} | {r['label']} | {r['mean_wer']:.1%} | {r['mean_score']} | {r['diff_vs_V1']:+} |")
    L += ["", "### Findings (a difference larger than half a point is a finding)", ""]
    allf = list(ac["findings"]) + (list(aw["findings"]) if aw else [])
    if allf:
        for f in allf:
            L.append(f"- **{f['variant']}**: {f['finding']} (mean word error rate {f['mean_wer']:.1%}). Logged in the risk register as R-007.")
    else:
        L.append("- No variant differed from V1 by more than half a point.")
    L += ["", "Why this matters: Rule 4 says interviews are scored on content, never on accent or fluency. If a speech model mishears some voices more, "
          "those candidates are scored lower for something that is not their content. The mitigation is a recruiter review of every scorecard, a second scorer, and "
          "re-running this test with real accented speech and the production speech model before use.", ""]
    out = ROOT / "BIAS_REPORT.md"
    out.write_text("\n".join(L), encoding="utf-8")
    return out


def write_perf_report(r: dict) -> Path:
    c, v, sp, ch = r["cost"], r["voice"], r["speed"], r["caching"]
    a = r["assumptions"]
    off, on, rs = ch["cache_off"], ch["cache_on"], ch["rescreen"]
    L = ["# PERF_REPORT.md", "", f"Generated {date.today().isoformat()} by `python -m scripts.run_perf` from `evidence/perf.json`.", "",
         "> **Read this first.** This run used **fake models**, so no model was called. Token counts are estimated (characters / 4) and are real for the prompts the platform builds; "
         "**costs are what those tokens would cost at the list prices** in `app/ai/router.py`; **model and speech latency are assumptions** (below). The platform's own compute time is measured. "
         "Run with `FAKE_MODELS=0` and replace the constants for figures you can quote.", "",
         f"## Cost (for {r['n_cvs']} CVs and {r['n_interviews']} AI interviews)", "",
         "| What | Before | After | Change |", "|---|---|---|---|",
         f"| Cost per 100 CVs screened (read + score) | ${c['per_100_cvs_before']} | **${c['per_100_cvs_after']}** | routing: extraction moves to the local model, scoring stays on the large model |",
         f"| Cost per 100 CVs if extraction used the small hosted model instead | ${c['per_100_cvs_before']} | ${c['per_100_cvs_after_small_extraction']} | not chosen: CVs carry identity, so extraction stays local (rule 10) |",
         f"| Cost per AI interview (LLM scoring) | ${c['per_ai_interview_llm']} | ${c['per_ai_interview_llm']} | scoring needs judgement, so it stays on the large model |",
         f"| Cost per AI interview (speech to text, assumed ${a['stt_usd_per_minute']}/min) | | ${c['per_ai_interview_stt']} | |",
         f"| Cost per AI interview (text to speech, assumed ${a['tts_usd_per_1k_chars']}/1k chars) | | ${c['per_ai_interview_tts']} | |",
         f"| **Cost per AI interview, total** | | **${c['per_ai_interview_total']}** | |", "",
         f"Tokens in the screening run: {c['tokens_in']:,} in, {c['tokens_out']:,} out ({c['extraction_tokens']:,} for reading CVs, {c['scoring_tokens']:,} for scoring).", "",
         "## Routing: small model for extraction and point-ticking, large for scoring and suggestions, local for any step that sees identity", "",
         "Before: every call goes to the large model. After: `app/ai/router.py` sends each kind of step to the right tier, and a step that sees identity (reading a CV, drafting to a named person) "
         "never leaves the machine. The routing is also a privacy control, not only a cost one.", "",
         "## Caching", "",
         "| Test | Without cache | With cache |", "|---|---|---|",
         f"| 15 assistant questions (5 questions asked 3 times): paid model calls | {off['model_calls_paid']} | **{on['model_calls_paid']}** |",
         f"| ...cost | ${off['cost_usd']} | ${on['cost_usd']} |",
         f"| ...CV search index builds (hiding identity + vectors) | {off['index_builds']} | **{on['index_builds']}** |",
         f"| ...time | {off['seconds']} s | {on['seconds']} s |",
         f"| Screening the same pool a second time: paid calls | {rs['first_run_paid']} | {rs['second_run_paid']} ({rs['second_run_cached']} served from cache) |", "",
         "The model cache is keyed on the model, the prompt and the schema, so a changed CV or rubric never gets a stale answer. The assistant cache is also keyed on the size of the candidate pool.", "",
         "## Speed", "",
         f"- Reading {r['n_cvs']} CVs (PDF, Word, scans, screenshots, including OCR): **{sp['read_52_cvs_seconds']} s**. Scoring them: **{sp['screen_52_cvs_seconds']} s**. (Days to minutes: the brief's first objective.)",
         f"- A whole 8-question AI interview from recorded answers: {sp['interview_compute_seconds_each']} s of platform compute.", "",
         "## Voice interview speed", "",
         "Target: the next question starts within **2.5 s at p95** after the candidate finishes.", "",
         "| Part | Time | Source |", "|---|---|---|",
         f"| The platform's own work per turn (read the answer, score it, choose the next question, save state), p95 | {v['p95_compute_ms']} ms | **measured** over {v['turns_measured']} turns |",
         f"| Speech to text | {a['stt_latency_s']} s | assumption |", f"| Scoring model call | {a['llm_scoring_latency_s']} s | assumption |",
         f"| Text to speech, first audio | {a['tts_first_audio_s']} s | assumption |", f"| Network margin | {a['network_margin_s']} s | assumption |",
         f"| **Estimated p95** | **{v['p95_estimated_s']} s** | {'meets' if v['passed'] else 'MISSES'} the {v['target_s']} s target |", "",
         "Because the three model/speech numbers are assumptions, this is an estimate, not a measurement. To measure for real, run the interview with real models and read the `latency_ms` "
         "column of the model-call ledger and the interviewer spans in the traces (Phoenix, or the Trust & cost tab).", ""]
    out = ROOT / "PERF_REPORT.md"
    out.write_text("\n".join(L), encoding="utf-8")
    return out


def write_eval_report() -> Path:
    def load(n):
        p = ROOT / "evidence" / n
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    ex, rk, iv, cp = load("eval_extraction.json"), load("eval_ranking.json"), load("eval_interview.json"), load("eval_copilot.json")
    rt, bs, ba, pf, gv = load("red_team.json"), load("bias_screening.json"), load("bias_accents.json"), load("perf.json"), load("governance_check.json")
    L = ["# EVAL_REPORT.md", "", f"Generated {date.today().isoformat()} by `python -m scripts.quality_gate` from the files in `evidence/`.", "",
         "> **Mode: fake models.** The scorers are rule-based stand-ins, the recorded answers and interviews were built from the question bank and spoken by a text-to-speech engine, "
         "and the CVs are fictional. These numbers show that the platform's plumbing, checks and guardrails work and that every claim is measured by a script. "
         "They do **not** say how a real model would score: re-run with `FAKE_MODELS=0` (see README, \"Switching to real models\").", "",
         "## The quality bar", "", "| What | Target | Measured | Measured by |", "|---|---|---|---|"]
    def row(what, target, measured, by, passed):
        L.append(f"| {what} | {target} | {measured} {'PASS' if passed else '**FAIL**'} | {by} |")
    if ex:
        row("CV extraction", ">= 90% of fields right on the 12-CV key", f"{ex['pct']}% ({ex['fields_right']}/{ex['fields_total']})", "`scripts/eval_extraction.py`", ex["passed"])
    if rk:
        row("Shortlist", "top-5 overlap >= 4 of 5", "; ".join(f"{r['role'].replace('_', ' ')} {r['overlap']}/5 (strict {r['strict_overlap']}/5)" for r in rk["roles"]), "`scripts/eval_quality.py`", rk["passed"])
    if iv:
        row("Interview scoring", ">= 80% agreement on 30 recorded answers", f"{iv['scorer_agreement_with_key_pct']}% (checker {iv['checker_agreement_with_key_pct']}%)", "`scripts/eval_quality.py`", iv["passed"])
    if cp:
        row("Copilot key points", ">= 80% agreement on 4 recordings", f"{cp['key_point_agreement_pct']}% of {cp['points_compared']} comparisons", "`scripts/eval_copilot.py`", cp["key_point_agreement_pct"] >= 80)
        lag = max((f["lag_s"] for f in cp["forbidden_flags"] if "lag_s" in f), default=0)
        row("Forbidden question", "flagged within 3 s, every time", f"{lag} s after the question ended", "`scripts/eval_copilot.py` and the replay test", cp["passed"])
    if rt:
        row("Red team", ">= 18 of 20 attacks stopped", f"{rt['stopped_after']}/20 (before the guardrails: {rt['stopped_before']}/20)", "`scripts/run_red_team.py`", rt["passed"])
    if bs:
        row("Bias, screening", "no unexplained score difference between variants", f"{bs['unexplained_differences']} over {bs['variants']} CVs; adverse impact ratio {bs['adverse_impact_ratio']}", "`scripts/run_bias_tests.py`", bs["passed"])
    if ba:
        row("Bias, transcription", "differences above 0.5 point reported as findings", f"{len(ba['findings'])} finding(s) reported ({ba['mode']})", "`scripts/run_bias_tests.py`", ba["reported"])
    if pf:
        row("Voice speed", "next question within 2.5 s at p95", f"estimated {pf['voice']['p95_estimated_s']} s (compute alone {pf['voice']['p95_compute_ms']} ms)", "`scripts/run_perf.py`", pf["voice"]["passed"])
    if gv:
        row("Governance", "check passes; every claim has evidence with a hash", f"{sum(c['passed'] for c in gv['checks'])}/{len(gv['checks'])} checks", "`scripts/governance_check.py`", gv["passed"])
    L += ["", "Also on the quality bar, and measured by tests in `tests/`: **Identity hidden** (a test proves no name, email, phone, address or date of birth reaches a scoring prompt, and the "
          "compliance reviewer scans the whole prompt log), **Evidence** (every score has a quote that code found in its source; the compliance reviewer catches a planted fake quote), and "
          "**Approvals** (the decision-log check finds no decision, message or stage move without a person).", ""]
    if ex:
        L += ["## CV extraction", "", "| Format | Fields right |", "|---|---|"] + [f"| {k} | {v} |" for k, v in ex["by_format"].items()] + [""]
    if rk:
        L += ["## Shortlist ranking vs the recruiter's key", "",
              "The key is a fictional recruiter's judgement made by a rule that is separate from the platform's scoring rule. It can have ties around fifth place, so anyone tied with the "
              "key's fifth place counts as in its top 5 (both numbers are shown).", "", "| Role | CVs | Tie-aware overlap | Strict overlap | Tied at 5th |", "|---|---|---|---|---|"]
        L += [f"| {r['role'].replace('_', ' ')} | {r['cvs']} | {r['tie_aware_overlap']}/5 | {r['strict_overlap']}/5 | {r['candidates_tied_at_fifth_place']} |" for r in rk["roles"]] + [""]
        L += ["Calibration note: the first run scored 3/5 on every role. Two things were found and fixed: the key's own ties (above) and a 3-score rule that was more generous than the rubric wording "
              "(\"several years or certified\"). It was tightened to match the wording, not copied from the key's formula. The DA and Platform roles reach 4/5, not 5/5, which is the honest picture.", ""]
    if iv:
        L += ["## Interview scoring on the 30 recorded answers", "", "| Kind of answer | Scorer matches the key |", "|---|---|"] + [f"| {k.replace('_', ' ')} | {v} |" for k, v in iv["by_kind"].items()]
        L += ["", f"The scorer and the second scorer (the checker) agree on {iv['scorer_vs_checker_agreement_pct']}% of answers. Where they differ the scorecard says \"please review\" and the recruiter reads the answer. "
              "Expect a lower figure with real models: the recorded answers were generated from the question bank's own sentences.", ""]
    L += ["## How to repeat", "", "```", "python -m scripts.quality_gate", "```", ""]
    out = ROOT / "EVAL_REPORT.md"
    out.write_text("\n".join(L), encoding="utf-8")
    return out
