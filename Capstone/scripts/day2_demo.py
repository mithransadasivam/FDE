"""Runs the whole of Day 2 in one command, in fake mode, and prints what it did (Day 2, end of day).

    python -m scripts.day2_demo

It screens every EXTRACTED candidate of the Cloud Support Engineer job, shortlists the top 6 as the recruiter (with a reason), invites the first
two, runs one interview with the STRONG simulated candidate and one with the WEAK one, builds both recordings and prints: candidates screened,
the verified quote rate, the shortlist, each interview's questions with skill and why, levels per skill, follow-ups and hints, the overall scores,
the recording files and today's decision log entries.

It needs the Day 1 data (python -m scripts.day1_demo): if the database is empty it runs that first. All data is fictional. Nothing is pushed or sent.
"""
import os
import subprocess
import sys
from datetime import datetime, timezone

os.environ.setdefault("FAKE_MODELS", "1")  # Day 2 is shown in fake mode: rule-based stand-ins, no key needed

from sqlalchemy import func, select  # noqa: E402

from app.agents.screening import screen_requisition  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.interview.recording import json_path, load_timeline, mp3_path  # noqa: E402
from app.interview.scorecard import build_card  # noqa: E402
from app.models import Candidate, DecisionLog, Requisition  # noqa: E402
from app.models_ext import InterviewSession, ItemScoreRow, ShortlistEntry  # noqa: E402
from app.privacy import identity_leaks, make_blind  # noqa: E402
from app.schemas import Stage  # noqa: E402
from app.shortlist import approve_shortlist, suggest_shortlist  # noqa: E402
from app.supervisor import move  # noqa: E402
from tests.sim.runner import run_interview  # noqa: E402

RECRUITER = "recruiter@example.com"
TOP = 6


def line(title: str) -> None:
    print(f"\n=== {title} " + "=" * max(3, 70 - len(title)))


def main() -> int:
    if not get_settings().fake_models:
        print("Day 2's demo runs in fake mode: set FAKE_MODELS=1.")
        return 1
    init_db()
    started = datetime.now(timezone.utc)
    with SessionLocal() as db:
        empty = not db.scalar(select(func.count()).select_from(Requisition))
    if empty:
        print("The database is empty: running the Day 1 demo first ...")
        if subprocess.run([sys.executable, "-m", "scripts.day1_demo"]).returncode != 0:
            return 1

    with SessionLocal() as db:
        req = db.scalars(select(Requisition).where(Requisition.title.ilike("%cloud support%"))).first()
        if req is None or req.status not in ("APPROVED", "PUBLISHED"):
            print("There is no approved Cloud Support Engineer job: run python -m scripts.day1_demo --reset")
            return 1

        line("1. Identity is hidden while scoring")
        cands = db.scalars(select(Candidate).where(Candidate.requisition_id == req.id)).all()
        leaks = sum(len(identity_leaks(make_blind(c), c)) for c in cands)
        print(f"{len(cands)} candidates; identity leaks in their blind records: {leaks}")

        line("2. Screening: every skill scored 0-3 with a quote that code verified")
        out = screen_requisition(db, req.id, RECRUITER)
        suggest_shortlist(db, req.id, top_n=TOP)
        rows = db.scalars(select(ItemScoreRow).where(ItemScoreRow.requisition_id == req.id)).all()
        nonzero = [r for r in rows if r.score > 0]
        verified = [r for r in nonzero if r.verified]
        print(f"Candidates screened: {out['scored']} (waiting in the review queue: {out['waiting_in_review']})")
        print(f"Verified quote rate: {len(verified)}/{len(nonzero)} non-zero scores = {100 * len(verified) / max(1, len(nonzero)):.1f}%; "
              f"a score whose quote is not found in the CV text is set to 0 by code")

        line(f"3. The recruiter shortlists the top {TOP} (nothing is shortlisted automatically)")
        suggested = [e for e in db.scalars(select(ShortlistEntry).where(ShortlistEntry.requisition_id == req.id).order_by(ShortlistEntry.rank)) if e.status == "SUGGESTED"][:TOP]
        screened_ids = [e.candidate_id for e in suggested if db.get(Candidate, e.candidate_id).stage == Stage.SCREENED.value]
        if screened_ids:
            approve_shortlist(db, req.id, screened_ids, RECRUITER, "Day 2 demo: the six highest totals, with every must-have evidenced")
        for e in suggested:
            print(f"  #{e.rank}  candidate {e.candidate_id}  {e.weighted_total}/100   {'; '.join(e.strengths or [])[:80]}")

        line("4. Invitations: the recruiter invites the first two, who each see the notice and agree to recording")
        free = [c for c in db.scalars(select(Candidate).where(Candidate.requisition_id == req.id, Candidate.stage.in_(["SHORTLISTED", "AI_INTERVIEW"])).order_by(Candidate.id))
                if not db.scalars(select(InterviewSession).where(InterviewSession.candidate_id == c.id, InterviewSession.status == "DONE")).first()][:2]
        if len(free) < 2:
            print("Fewer than two candidates are free for the demo interviews: run python -m scripts.day1_demo --reset first.")
            return 1
        for c in free:
            if c.stage == Stage.SHORTLISTED.value:
                move(db, c, Stage.AI_INTERVIEW, RECRUITER, "Day 2 demo: invited to the first-round AI interview")
        db.commit()
        print("  scoring scale: this project scores each answer against the question guide's 0-3 key points, so there is no separate 0-4 scale to prepare")

        line("5. Two complete adaptive interviews: a STRONG and a WEAK simulated candidate (labelled SAMPLE)")
        done = []
        for cand, persona in zip(free, ("strong", "weak")):
            res = run_interview(db, cand, req, persona)
            s = db.query(InterviewSession).filter_by(candidate_id=cand.id).one()
            card = build_card(db, s)
            done.append((cand, persona, s, card))
            print(f"\n--- candidate {cand.id} ({persona}) ---  interview {s.id}, ended: {res['scorecard']['ended_reason']}")
            for n, t in enumerate(s.state["turns"], 1):
                for m in t["meta"]:
                    if m["kind"] == "hint":
                        print(f"     hint given: {m['text'][:70]}")
                        continue
                    print(f"  Q  [{t['skill'] or 'opening'}] ({m['kind']}) {m['text'][:90]}")
                    print(f"        why: {m['why'][:100]}")

        line("6. Levels per skill, follow-ups, hints and the overall scores")
        for cand, persona, s, card in done:
            print(f"\ncandidate {cand.id} ({persona}): overall {card['overall_100']} / 100, must-haves covered: {card['all_must_haves_covered']}")
            for r in card["skills"]:
                if r["asked"]:
                    print(f"  {r['skill']:<36} level {r['level']}/3  second scorer {r['second_level']}  follow-ups {r['follow_ups']}  hints {r['hints']}"
                          + ("   <- scorers disagree: please review" if r["scorers_disagree"] else ""))
            print(f"  AI-written summary: {card['summary']['text']}")

        line("7. The full recordings")
        for cand, persona, s, card in done:
            tl = load_timeline(s)
            print(f"  candidate {cand.id} ({persona}): {mp3_path(s)}  ({tl['duration']} s, {len(tl['clips'])} clips)  timeline: {json_path(s)}")

        line("8. Today's decision log entries")
        entries = db.scalars(select(DecisionLog).where(DecisionLog.at >= started).order_by(DecisionLog.id)).all()
        for e in entries:
            who = e.actor if "@" in e.actor else f"({e.actor})"
            print(f"  {e.action:<46} {e.subject:<16} {who:<24} {e.reason[:60]}")
        print(f"\n{len(entries)} entries. A person made every shortlist and invitation move; the system only screened and recorded.")
    print("\nDay 2 demo complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
