"""Copilot evaluation (Day 4, prompt 4): how many of the planned moments in the practice interviews did the copilot catch, and how fast?

The practice interviews (app/practice.py) carry an answer key: five planned moments with the line each is on. Three more practice interviews are made
for different candidates (so there are at least four), the copilot is run on every one as if it were live, and each planned moment is checked:

  forbidden_question    was it warned, and how many seconds after the question ENDED (measured on the interview's own timeline; the time the code
                        needed is reported next to it)? Pass rule: every forbidden question is warned within 2 seconds.
  cv_conflict           was the CV-check card shown, with both what the candidate said and what the CV shows?
  vague_answer          was a follow-up suggested after the vague answer?
  good_technical_answer were most key points ticked (at least 3 of 4)?
  behavioural_answer    were most of Situation, Task, Action and Result heard?

False alarms are counted too: a warning or a CV card where no moment was planned.

    python -m evals.copilot_eval              (4x speed in fake mode; --speed 1 for real time; --speed 0 for instant)
Writes reports/copilot_eval.md and reports/copilot_eval.json (the Trust and cost page reads the warning times from the .json).
"""
import argparse
import sys
import time
from pathlib import Path

from sqlalchemy import select

from app.agents.copilot import CopilotAgent
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models import Candidate, Requisition
from app.practice import folder_for, load_practice, make_practice
from app.voice.replayer import replay
from evals.common import table, write_report

WITHIN_SECONDS = 2.0
MIN_PRACTICE = 4
NEW_PRACTICE = 3
KINDS = ["forbidden_question", "cv_conflict", "vague_answer", "good_technical_answer", "behavioural_answer"]


def ensure_practice(db) -> list[int]:
    """Makes NEW_PRACTICE more practice interviews for shortlisted candidates (different from any that already have one), and returns every candidate that has one."""
    have = [c for c in db.scalars(select(Candidate).order_by(Candidate.id)) if load_practice(c.id)]
    pool = [c for c in db.scalars(select(Candidate).where(Candidate.stage.in_(["SHORTLISTED", "AI_INTERVIEW", "HUMAN_INTERVIEW", "DECISION"])).order_by(Candidate.id))
            if not load_practice(c.id)]
    made = []
    for c in pool[:max(NEW_PRACTICE, MIN_PRACTICE - len(have))]:
        make_practice(db, c, speak_real=False)
        made.append(c.id)
    return sorted({c.id for c in have} | set(made))


def run_copilot(db, cand: Candidate, doc: dict, speed: float) -> dict:
    agent = CopilotAgent(db, cand, db.get(Requisition, cand.requisition_id))
    events, wall = [], []
    for turn in replay(doc, speed):
        t0 = time.perf_counter()
        out = agent.process_turn(turn["speaker"], turn["text"], turn["start"], turn["end"])
        wall.append((turn, time.perf_counter() - t0))
        events += out
    return {"agent": agent, "events": events, "wall": wall}


def line_of(doc: dict, n: int) -> dict:
    return doc["turns"][n - 1]  # moments count lines from 1


def evaluate(doc: dict, run: dict) -> dict:
    agent, events = run["agent"], run["events"]
    m = doc["moments"]
    out, matched_warn, matched_cards = {}, set(), set()

    # forbidden question: the warning for that exact line, and when it came, measured from the end of the question on the interview's timeline
    fm = m["forbidden_question"]
    ft = line_of(doc, fm["line"])
    warns = [w for w in agent.warnings if w["question"] == ft["text"]]
    if warns:
        w = warns[0]
        matched_warn.add(id(w))
        out["forbidden_question"] = {"caught": True, "seconds_after_question_ended": round(w["t"] - ft["end"], 3), "code_time_s": w["lag_s"], "found_by": w.get("found_by"),
                                     "answer_excluded": any(e["text"] for e in agent.excluded)}
    else:
        out["forbidden_question"] = {"caught": False}

    # CV conflict: a card with both quotes, on the candidate's claim
    cm = m["cv_conflict"]
    ct = line_of(doc, cm["line"])
    cards = [c for c in agent.conflicts if ct["start"] - 0.01 <= c["t"] <= ct["end"] + 1.0 and cm["skill"].lower() in (c.get("skill", "") + " " + c.get("text", "") + " " + c.get("said", "")).lower()]
    if cards:
        c = cards[0]
        matched_cards.add(id(c))
        both = bool(c.get("said") and c.get("cv"))
        out["cv_conflict"] = {"caught": True, "both_quotes": both, "said": c.get("said", ""), "cv": c.get("cv", "")}
    else:
        out["cv_conflict"] = {"caught": False, "both_quotes": False}

    # vague answer: a follow-up suggestion after it, before the next recruiter line is finished
    vm = m["vague_answer"]
    vt = line_of(doc, vm["line"])
    nxt = doc["turns"][vm["line"]]["end"] if vm["line"] < len(doc["turns"]) else vt["end"] + 5
    sugg = [e for e in events if e.kind == "suggestion" and vt["end"] - 0.01 <= e.t <= nxt + 0.01]
    follow = [i for e in sugg for i in e.data["items"] if "follow" in i.get("kind", "").lower() or "say more" in i.get("text", "").lower() or i.get("skill") == vm["skill"]]
    out["vague_answer"] = {"caught": bool(follow), "suggestion": (follow[0]["text"] if follow else "")}

    # good technical answer: most key points ticked
    gm = m["good_technical_answer"]
    total = len(gm["key_points"])
    ticked = len(agent.ticked.get(gm["question_id"], set()))
    out["good_technical_answer"] = {"caught": ticked >= max(1, round(0.75 * total)), "ticked": ticked, "of": total}

    # behavioural answer: STAR parts heard
    bm = m["behavioural_answer"]
    star = len(agent.ticked.get(bm["question_id"], set()))
    out["behavioural_answer"] = {"caught": star >= 3, "heard": star, "of": len(bm["star"])}

    false_warnings = [{"question": w["question"], "t": w["t"]} for w in agent.warnings if id(w) not in matched_warn]
    false_cards = [{"said": c.get("said", c.get("text", "")), "t": c["t"]} for c in agent.conflicts if id(c) not in matched_cards]
    return {"moments": out, "false_alarms": {"warnings": false_warnings, "cv_cards": false_cards}}


def main(speed: float | None = None) -> int:
    init_db()
    s = get_settings()
    if speed is None:
        speed = 4.0 if s.fake_models else 1.0
    with SessionLocal() as db:
        ids = ensure_practice(db)
        runs = []
        for cid in ids:
            cand = db.get(Candidate, cid)
            doc = load_practice(cid)
            run = run_copilot(db, cand, doc, speed)
            ev = evaluate(doc, run)
            runs.append({"candidate": cid, "duration_s": doc["duration_s"], "interview": str(folder_for(cid) / "practice.json"), **ev})
            wk = max((w for _t, w in run["wall"]), default=0.0)
            print(f"  candidate {cid}: " + ", ".join(f"{k}={'yes' if ev['moments'][k]['caught'] else 'NO'}" for k in KINDS) +
                  f"; false alarms {len(ev['false_alarms']['warnings']) + len(ev['false_alarms']['cv_cards'])}; slowest turn {wk * 1000:.0f} ms")
    per_kind = {k: {"caught": sum(1 for r in runs if r["moments"][k]["caught"]), "planned": len(runs)} for k in KINDS}
    times = [r["moments"]["forbidden_question"]["seconds_after_question_ended"] for r in runs if r["moments"]["forbidden_question"]["caught"]]
    code_times = [r["moments"]["forbidden_question"]["code_time_s"] for r in runs if r["moments"]["forbidden_question"]["caught"]]
    fa_w = sum(len(r["false_alarms"]["warnings"]) for r in runs)
    fa_c = sum(len(r["false_alarms"]["cv_cards"]) for r in runs)
    all_warned = per_kind["forbidden_question"]["caught"] == len(runs)
    passed = bool(runs) and all_warned and bool(times) and max(times) <= WITHIN_SECONDS
    results = {"interviews": len(runs), "per_kind": per_kind, "warning_seconds_average": round(sum(times) / len(times), 4) if times else None,
               "warning_seconds_slowest": max(times) if times else None, "code_seconds_slowest": max(code_times) if code_times else None,
               "false_alarms": {"warnings": fa_w, "cv_cards": fa_c}, "runs": runs}
    md = ["## Pass rule", f"Every forbidden question must be warned within {WITHIN_SECONDS:g} seconds of the question ending. Warned: **{per_kind['forbidden_question']['caught']} of {len(runs)}**; "
          f"slowest warning **{results['warning_seconds_slowest']} s** after the question ended.", "",
          "## Caught out of planned", table(["moment", "caught", "planned"], [[k, v["caught"], v["planned"]] for k, v in per_kind.items()]), "",
          "## Warning time (seconds after the forbidden question ended, on the interview's own timeline)",
          f"Average **{results['warning_seconds_average']} s**, slowest **{results['warning_seconds_slowest']} s**. This is the time the copilot needed after the question ended; "
          "a live deployment adds the speech-to-text delay on top.", "",
          "## False alarms", f"Warnings where no forbidden question was planned: **{fa_w}**. CV-check cards where no conflict was planned: **{fa_c}**."]
    for r in runs:
        for w in r["false_alarms"]["warnings"]:
            md.append(f"- candidate {r['candidate']}: warning for \"{w['question'][:80]}\" at {w['t']} s")
        for c in r["false_alarms"]["cv_cards"]:
            md.append(f"- candidate {r['candidate']}: CV card at {c['t']} s: \"{c['said'][:80]}\"")
    md += ["", "## By interview", table(["candidate", *KINDS, "false alarms"], [[r["candidate"], *[("yes" if r["moments"][k]["caught"] else "MISSED") for k in KINDS],
                                                                                 len(r["false_alarms"]["warnings"]) + len(r["false_alarms"]["cv_cards"])] for r in runs]), "",
           "## Limits", "- The practice interviews are scripted and fictional: the copilot is tested on moments we planned, in clean text. Real, unplanned interviews will be harder (accents, overlap, "
           "speech-to-text errors); test those with a person scoring the copilot's cards.",
           f"- Ran in {'fake mode (rule-based)' if s.fake_models else 'real-model mode'} at {speed:g}x. A missed moment can mean the key words did not match, not that it was missed by a person.", ""]
    write_report("copilot_eval", "Copilot evaluation", {"speed": speed, "within_seconds": WITHIN_SECONDS, "interviews": ids, "mode": "fake" if s.fake_models else "real"}, results, passed, "\n".join(md))
    print(f"Copilot eval: {len(runs)} interviews; forbidden questions {per_kind['forbidden_question']['caught']}/{len(runs)}, slowest warning {results['warning_seconds_slowest']} s; "
          f"false alarms {fa_w + fa_c}; {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 2


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--speed", type=float, default=None)
    sys.exit(main(ap.parse_args().speed))
