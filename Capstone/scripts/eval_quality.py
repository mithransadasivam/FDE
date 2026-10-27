"""Evaluations behind the quality bar (Day 2 role D): ranking vs the recruiter's key, and AI-interview scoring vs the 30 expected scores.

Run:  python -m scripts.eval_quality        (writes evidence/eval_ranking.json and evidence/eval_interview.json)
Targets: top-5 overlap at least 4 of 5; interview scoring agrees with the key on at least 80% of the 30 recorded answers.

Honest note for fake mode: the scorers here are rule-based stand-ins, and the recorded answers were built from the question bank, so
these numbers show that the plumbing and the checks work. Run with real models (FAKE_MODELS=0) for the figures that matter.
"""
import json
import sys
from pathlib import Path

from app.agents.document import extract_profile
from app.agents.interviewer import score_text, second_opinion
from app.agents.requisition import generate_job
from app.agents.screening import score_blind
from app.config import get_settings
from app.db import init_db
from app.interview.bank import load_questions
from app.interview.replay import load_recorded
from app.models import Candidate
from app.privacy import make_blind

KIT = Path(get_settings().kit_dir)
ROLE_NOTES = {"cloud_support_engineer": "REQ_cloud_support_engineer", "data_analyst": "REQ_data_analyst", "platform_engineer": "REQ_platform_engineer"}
FOLDERS = {"cloud_support_engineer": "cloud_support_engineer", "data_analyst": "data_analyst", "platform_engineer": "platform_engineer"}


def rank_role(role: str) -> dict:
    key = json.loads((KIT / "answer_keys" / f"ranking_key_{role}.json").read_text(encoding="utf-8"))
    rubric = generate_job((KIT / "voice_notes" / f"{ROLE_NOTES[role]}.transcript.txt").read_text(encoding="utf-8")).rubric
    scored = []
    for row in key["candidates"]:
        profile = extract_profile(KIT / "cvs" / FOLDERS[role] / row["file"])
        cand = Candidate(id=len(scored) + 1, requisition_id=1, cv_path="", cv_name=row["file"], cv_format="x", access_token="t", profile=profile.model_dump())
        res = score_blind(make_blind(cand), rubric, cand.id)
        scored.append((row["file"], res.weighted_total))
    scored.sort(key=lambda x: (-x[1], x[0]))
    ours = [f for f, _ in scored[:5]]
    strict = len(set(ours) & set(key["shortlist_top5"]))
    # The key can have ties around fifth place (the recruiter had no preference between tied candidates), so anyone tied with the
    # key's fifth place counts as in the key's top 5. Both numbers are reported; the gate uses the tie-aware one.
    totals = {c["file"]: c["total"] for c in key["candidates"]}
    cutoff = sorted(totals.values(), reverse=True)[4]
    overlap = sum(1 for f in ours if totals[f] >= cutoff)
    tied = sum(1 for v in totals.values() if v == cutoff)
    return {"role": role, "cvs": len(scored), "platform_top5": ours, "recruiter_top5": key["shortlist_top5"], "strict_overlap": strict,
            "tie_aware_overlap": overlap, "candidates_tied_at_fifth_place": tied, "overlap": overlap, "passed": overlap >= 4}


def eval_ranking() -> dict:
    roles = [rank_role(r) for r in ROLE_NOTES]
    return {"roles": roles, "target_overlap": 4, "passed": all(r["passed"] for r in roles)}


def eval_interview() -> dict:
    bank, answers = load_questions(), load_recorded()
    rows, first, second = [], 0, 0
    for a in answers:
        q = bank[a["question_id"]]
        s1 = score_text(q, a["text"]).score
        s2 = second_opinion(q, a["text"])
        first += s1 == a["expected_score"]
        second += s2 == a["expected_score"]
        rows.append({"id": a["id"], "question": a["question_id"], "kind": a["kind"], "expected": a["expected_score"], "scorer": s1, "checker": s2})
    agree = sum(r["scorer"] == r["checker"] for r in rows)
    n = len(answers)
    pct = round(100 * first / n, 1)
    return {"answers": n, "scorer_agreement_with_key_pct": pct, "checker_agreement_with_key_pct": round(100 * second / n, 1),
            "scorer_vs_checker_agreement_pct": round(100 * agree / n, 1), "details": rows, "target_pct": 80, "passed": pct >= 80,
            "by_kind": {k: f"{sum(1 for r in rows if r['kind'] == k and r['scorer'] == r['expected'])}/{sum(1 for r in rows if r['kind'] == k)}" for k in sorted({r['kind'] for r in rows})}}


def main() -> int:
    init_db()
    out = Path("evidence")
    out.mkdir(exist_ok=True)
    rk, iv = eval_ranking(), eval_interview()
    (out / "eval_ranking.json").write_text(json.dumps(rk, indent=1), encoding="utf-8")
    (out / "eval_interview.json").write_text(json.dumps(iv, indent=1), encoding="utf-8")
    for r in rk["roles"]:
        print(f"Ranking {r['role']}: top-5 overlap {r['overlap']}/5 (strict {r['strict_overlap']}/5, {r['candidates_tied_at_fifth_place']} tied at 5th place) over {r['cvs']} CVs (target: at least 4)  {'PASS' if r['passed'] else 'FAIL'}")
    print(f"Interview scoring: {iv['scorer_agreement_with_key_pct']}% agree with the key on {iv['answers']} answers (target: at least 80%); "
          f"checker {iv['checker_agreement_with_key_pct']}%; scorer and checker agree on {iv['scorer_vs_checker_agreement_pct']}%  {'PASS' if iv['passed'] else 'FAIL'}")
    return 0 if rk["passed"] and iv["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
