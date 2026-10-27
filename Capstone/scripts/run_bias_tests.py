"""Bias tests (Day 4, BR-16).

1. Screening, counterfactual: 6 CVs x 5 versions where ONLY the name, gender clues or age clues change. Each version goes through the whole
   pipeline (read the CV, hide identity, score). Any score difference between versions of the same CV is an unexplained difference.
   Selection rates by fictional group are reported with the four-fifths rule.
2. Transcription: the same 5 answers spoken in 4 voice variants, transcribed, then scored. Word error rate and mean score per variant;
   any score difference larger than half a point is a FINDING (it goes in the risk register).

IMPORTANT, said plainly: the Windows speech engine has two voices (US male and US female); the four "accents" are four speaking styles
(pace and pitch), NOT real accents. A real accent test needs recorded speakers with real accents. Default mode uses simulated recognition
errors; `--whisper` transcribes the audio with a real speech model (faster-whisper) and measures real word error rates.

Run:  python -m scripts.run_bias_tests              (simulated recognition, fast, used by the tests)
      python -m scripts.run_bias_tests --whisper    (real Whisper on the audio; downloads a small model the first time)
Writes evidence/bias_screening.json, evidence/bias_accents.json (and bias_accents_whisper.json) and BIAS_REPORT.md.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from app.agents.document import extract_profile
from app.agents.interviewer import score_text
from app.agents.requisition import generate_job
from app.agents.screening import score_blind
from app.config import get_settings
from app.db import init_db
from app.evidence import blind_text
from app.guardrails import scan_protected
from app.interview.bank import load_questions
from app.models import Candidate
from app.privacy import identity_strings, make_blind

KIT = Path(get_settings().kit_dir)
THRESHOLD = 60.0  # a fictional selection rule: a weighted total of 60 or more is shortlisted
EVIDENCE = Path("evidence")


def rubric():
    return generate_job((KIT / "voice_notes" / "REQ_cloud_support_engineer.transcript.txt").read_text(encoding="utf-8")).rubric


def screening_test() -> dict:
    manifest = json.loads((KIT / "bias_variants" / "manifest.json").read_text(encoding="utf-8"))
    rb = rubric()
    rows, diffs, leaks = [], 0, 0
    by_group: dict[str, list[float]] = {}
    for v in manifest["variants"]:
        profile = extract_profile(KIT / "bias_variants" / v["file"])
        cand = Candidate(id=v["base"], requisition_id=1, cv_path="", cv_name=v["file"], cv_format="docx", access_token="t", profile=profile.model_dump())
        blind = make_blind(cand)
        res = score_blind(blind, rb, cand.id)
        text = blind_text(blind)
        leaks += len(scan_protected(text, identity_strings(cand.profile)))
        rows.append({"base": v["base"], "kind": v["kind"], "total": res.weighted_total, "scores": [i.score for i in res.items], "blind_text": text,
                     "extracted": {"name": profile.name.value, "date_of_birth": profile.date_of_birth.value}})
        by_group.setdefault(v["kind"], []).append(res.weighted_total)
    bases = sorted({r["base"] for r in rows})
    detail = []
    for b in bases:
        group = [r for r in rows if r["base"] == b]
        ref = next(r for r in group if r["kind"] == "original")
        for r in group:
            same_score = r["scores"] == ref["scores"] and r["total"] == ref["total"]
            same_blind = r["blind_text"] == ref["blind_text"]
            if not same_score:
                diffs += 1
            detail.append({"base": b, "kind": r["kind"], "total": r["total"], "same_scores_as_original": same_score, "same_blind_record_as_original": same_blind,
                           "name_in_cv": r["extracted"]["name"]})
    rates = {k: round(sum(t >= THRESHOLD for t in v) / len(v), 3) for k, v in by_group.items()}
    ratio = round(min(rates.values()) / max(rates.values()), 3) if max(rates.values()) else 1.0
    return {"variants": len(rows), "bases": len(bases), "unexplained_differences": diffs, "identity_leaks_in_prompts": leaks, "selection_threshold": THRESHOLD,
            "selection_rate_by_group": rates, "adverse_impact_ratio": ratio, "four_fifths_rule_ok": ratio >= 0.8, "details": detail,
            "passed": diffs == 0 and leaks == 0 and ratio >= 0.8,
            "method": "each CV file is read, identity is hidden (make_blind) and the blind record is scored by the production path (score_blind)"}


# ---- transcription fairness ---------------------------------------------------------------------------------------------------------
HOMOPHONES = {"swap": "swamp", "disk": "desk", "logs": "lugs", "queue": "cue", "replica": "replicate", "failover": "fail over", "dns": "dnz",
              "traceroute": "trace route", "kubernetes": "cuber nettys", "terraform": "tear a form", "grafana": "grafanna", "latency": "late and see",
              "acknowledge": "a knowledge", "memory": "memoir", "route": "root", "table": "tablet", "cpu": "see pea you", "uptime": "up time"}
STEP = {"V1": 0, "V2": 0, "V3": 14, "V4": 7}  # simulated: V3/V4 make an error roughly every 14th/7th word that has a confusable


def simulate_asr(text: str, variant: str) -> str:
    """SIMULATED recognition errors: confusable words are mis-heard at a fixed rate that grows from V1 to V4. Deterministic."""
    step = STEP[variant]
    if not step:
        return text
    words, out, n = text.split(), [], 0
    for w in words:
        key = re.sub(r"[^a-z]", "", w.lower())
        if key in HOMOPHONES:
            n += 1
            if n % max(1, step // 7) == 0:
                w = HOMOPHONES[key] + (w[-1] if w[-1] in ".,?!" else "")
        out.append(w)
    return " ".join(out)


def wer(ref: str, hyp: str) -> float:
    r = re.sub(r"[^a-z0-9 ]", "", ref.lower()).split()
    h = re.sub(r"[^a-z0-9 ]", "", hyp.lower()).split()
    d = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        prev, d[0] = d[0], i
        for j, hw in enumerate(h, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (rw != hw))
    return round(d[len(h)] / max(1, len(r)), 4)


def whisper_transcriber():
    from faster_whisper import WhisperModel
    model = WhisperModel("tiny.en", device="cpu", compute_type="int8")

    def run(path: Path) -> str:
        segs, _ = model.transcribe(str(path), language="en", vad_filter=False)
        return " ".join(s.text.strip() for s in segs)
    return run


def accent_test(use_whisper: bool) -> dict:
    clips = json.loads((KIT / "accent_set" / "accents.json").read_text(encoding="utf-8"))
    bank = load_questions()
    asr = whisper_transcriber() if use_whisper else None
    by_variant: dict[str, dict] = {}
    for c in clips:
        hyp = asr(KIT / c["file"]) if asr else simulate_asr(c["text"], c["voice"])
        s = score_text(bank[c["question_id"]], hyp).score
        v = by_variant.setdefault(c["voice"], {"label": c["label"], "wers": [], "scores": []})
        v["wers"].append(wer(c["text"], hyp))
        v["scores"].append(s)
    base = sum(by_variant["V1"]["scores"]) / len(by_variant["V1"]["scores"])
    rows, findings = [], []
    for k, v in sorted(by_variant.items()):
        mean = round(sum(v["scores"]) / len(v["scores"]), 2)
        row = {"variant": k, "label": v["label"], "mean_wer": round(sum(v["wers"]) / len(v["wers"]), 4), "mean_score": mean, "diff_vs_V1": round(mean - base, 2), "scores": v["scores"]}
        rows.append(row)
        if abs(row["diff_vs_V1"]) > 0.5:
            findings.append({"variant": k, "diff_vs_V1": row["diff_vs_V1"], "mean_wer": row["mean_wer"],
                             "finding": f"Scores for {v['label']} differ from {by_variant['V1']['label']} by {row['diff_vs_V1']} points (more than half a point)."})
    mode = "faster-whisper tiny.en on synthesised audio (measured)" if use_whisper else "SIMULATED recognition errors (no speech model run)"
    return {"mode": mode, "variants": rows, "findings": findings, "reported": True, "clips": len(clips),
            "limitation": "voice variants made with a text-to-speech engine, not real accents: a real accent test needs real speakers"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--whisper", action="store_true")
    args = ap.parse_args()
    init_db()
    EVIDENCE.mkdir(exist_ok=True)
    sc = screening_test()
    (EVIDENCE / "bias_screening.json").write_text(json.dumps(sc, indent=1), encoding="utf-8")
    ac = accent_test(False)
    (EVIDENCE / "bias_accents.json").write_text(json.dumps(ac, indent=1), encoding="utf-8")
    aw = None
    if args.whisper:
        try:
            aw = accent_test(True)
            (EVIDENCE / "bias_accents_whisper.json").write_text(json.dumps(aw, indent=1), encoding="utf-8")
        except Exception as e:  # e.g. the model could not be downloaded
            print(f"Real Whisper run failed ({type(e).__name__}: {str(e)[:120]}); the simulated results stand.")
    from scripts.reports import write_bias_report
    write_bias_report(sc, ac, aw if aw else (json.loads((EVIDENCE / "bias_accents_whisper.json").read_text()) if (EVIDENCE / "bias_accents_whisper.json").exists() else None))
    print(f"Screening: {sc['unexplained_differences']} unexplained differences over {sc['variants']} CV versions; identity leaks in prompts: {sc['identity_leaks_in_prompts']}; "
          f"adverse impact ratio {sc['adverse_impact_ratio']}  {'PASS' if sc['passed'] else 'FAIL'}")
    for label, a in (("simulated", ac), ("whisper", aw)):
        if a:
            print(f"Accents ({label}): " + "; ".join(f"{r['variant']} WER {r['mean_wer']:.0%} score {r['mean_score']} ({r['diff_vs_V1']:+})" for r in a["variants"]) + f"; {len(a['findings'])} finding(s)")
    return 0 if sc["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
