"""Copilot evaluation (Day 3): key points ticked vs the answer key on the 4 recorded interviews, and the forbidden question's flag time.

Ground truth for a key point is whether the candidate's turn really contains that point's sentence from the question bank (the recordings
were built from it), which is independent of the keyword matching the copilot uses.

Run:  python -m scripts.eval_copilot          (writes evidence/eval_copilot.json)
Targets: key points agree on at least 80%; the forbidden question is flagged within 3 seconds, every time.
"""
import json
import sys
from pathlib import Path

from app.agents.copilot import CopilotAgent
from app.agents.document import extract_profile
from app.config import get_settings
from app.db import init_db
from app.interview.bank import load_questions
from app.models import Candidate, Requisition
from app.voice.replayer import load_interviews, replay

FLAG_LIMIT_S = 3.0
RUBRIC = {"items": [{"skill": s, "weight": w, "must_have": False, "evidence_from_note": s} for s, w in
                    [("Linux troubleshooting", 19), ("Cloud networking", 19), ("Incident handling", 19), ("Scripting (Python or Bash)", 12),
                     ("Customer communication", 12), ("Kubernetes", 7), ("Terraform", 6), ("Monitoring (Prometheus, Grafana)", 6)]], "min_years": 2}


def expected_points(qid: str, text: str) -> set[int]:
    q = load_questions()[qid]
    low = text.lower()
    return {n for n, d in enumerate(q["key_point_detail"], 1) if d["say"][1:].lower() in low}


def run_one(interview: dict, speed: float = 0.0) -> tuple[CopilotAgent, list]:
    kit = Path(get_settings().kit_dir)
    profile = extract_profile(kit / "cvs" / "cloud_support_engineer" / interview["cv_file"])
    cand = Candidate(id=0, requisition_id=1, cv_path="", cv_name=interview["cv_file"], cv_format="pdf", access_token="x", profile=profile.model_dump())
    req = Requisition(id=1, title="Cloud Support Engineer", created_by="x", rubric=RUBRIC)
    agent = CopilotAgent(None, cand, req)
    events = []
    for turn in replay(interview, speed):
        events += agent.process_turn(turn["speaker"], turn["text"], turn["start"], turn["end"])
    return agent, events


def evaluate() -> dict:
    init_db()
    agree = total = 0
    rows, flags = [], []
    for iv in load_interviews():
        agent, events = run_one(iv)
        cur_q = None
        for t in iv["turns"]:
            if t["speaker"] == "recruiter":
                from app.agents.copilot import _match_question
                cur_q = _match_question(t["text"]) or cur_q if not t.get("forbidden") else None
                continue
            qid = t.get("qid")
            if not qid or qid not in load_questions() or load_questions()[qid]["type"] != "technical" or t.get("conflict"):
                continue
            exp, got = expected_points(qid, t["text"]), agent.ticked.get(qid, set())
            for n in range(1, len(load_questions()[qid]["key_points"]) + 1):
                total += 1
                agree += (n in exp) == (n in got)
            rows.append({"interview": iv["id"], "question": qid, "expected": sorted(exp), "copilot": sorted(got)})
        for w in agent.warnings:
            flags.append({"interview": iv["id"], "category": w["category"], "lag_s": w["lag_s"], "within_limit": w["t"] - w["question_ended"] <= FLAG_LIMIT_S})
        forbidden_expected = [t for t in iv["turns"] if t.get("forbidden")]
        if len(forbidden_expected) != len(agent.warnings):
            flags.append({"interview": iv["id"], "problem": f"expected {len(forbidden_expected)} warning(s), got {len(agent.warnings)}"})
    pct = round(100 * agree / total, 1) if total else 0
    ok = pct >= 80 and flags and all(f.get("within_limit") for f in flags if "within_limit" in f) and not any("problem" in f for f in flags)
    return {"key_point_agreement_pct": pct, "points_compared": total, "forbidden_flags": flags, "details": rows, "passed": bool(ok),
            "targets": {"key_points_min_pct": 80, "flag_within_s": FLAG_LIMIT_S}}


def main() -> int:
    r = evaluate()
    out = Path("evidence")
    out.mkdir(exist_ok=True)
    (out / "eval_copilot.json").write_text(json.dumps(r, indent=1), encoding="utf-8")
    print(f"Key points agree on {r['key_point_agreement_pct']}% of {r['points_compared']} comparisons (target: at least 80%)")
    for f in r["forbidden_flags"]:
        print("  forbidden question:", f)
    print("PASS" if r["passed"] else "FAIL")
    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
