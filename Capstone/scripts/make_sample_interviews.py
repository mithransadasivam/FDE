"""Makes sample interviews with simulated candidates (Day 2, prompt 13): a strong, a weak and a trickster candidate answer the live questions
for the Cloud Support Engineer job. The interviewer and the candidate are spoken with two DIFFERENT text-to-speech voices, the whole conversation
is joined into one recording, and every one of these interviews is marked as a sample and shown everywhere as "SAMPLE: fictional candidate".

    python -m scripts.make_sample_interviews

The app must already hold the job and candidates (python -m scripts.day1_demo or scripts.run_journey). Candidates are moved on the way (screened,
shortlisted, invited) as the recruiter, with a reason that says it is a sample. Everything here is fictional.
"""
import sys

from sqlalchemy import select

from app.agents.screening import screen_requisition
from app.db import SessionLocal, init_db
from app.interview.recording import mp3_path
from app.models import Candidate, DecisionLog, Requisition
from app.models_ext import InterviewSession
from app.schemas import Stage
from app.shortlist import approve_shortlist, suggest_shortlist
from app.supervisor import move
from tests.sim.runner import run_interview

RECRUITER = "recruiter@example.com"
PERSONAS = ["strong", "weak", "trickster"]
PROFILES = {"strong": {"role": "Cloud Support Engineer", "employer": "Harbourline Retail", "years": 6},
            "weak": {"role": "Service Desk Analyst", "employer": "Copperleaf Insurance", "years": 1},
            "trickster": {"role": "IT Support Analyst", "employer": "Bluefen Energy", "years": 2}}


def free_candidates(db, req: Requisition, n: int) -> list[Candidate]:
    """n candidates who have no interview yet, brought to AI_INTERVIEW by the recruiter (with a reason that says it is a sample)."""
    reason = "sample interview with a simulated candidate (fictional)"
    taken = {i.candidate_id for i in db.scalars(select(InterviewSession))}
    pool = lambda *stages: [c for c in db.scalars(select(Candidate).where(Candidate.requisition_id == req.id, Candidate.stage.in_(stages)).order_by(Candidate.id)) if c.id not in taken]
    if len(pool("SHORTLISTED", "AI_INTERVIEW")) < n:
        if len(pool("SCREENED")) < n and pool("EXTRACTED"):
            screen_requisition(db, req.id, RECRUITER)
            suggest_shortlist(db, req.id)
        screened = pool("SCREENED")[: n - len(pool("SHORTLISTED", "AI_INTERVIEW"))]
        if screened:
            approve_shortlist(db, req.id, [c.id for c in screened], RECRUITER, reason)
    chosen = pool("SHORTLISTED", "AI_INTERVIEW")[:n]
    for c in chosen:
        if c.stage == Stage.SHORTLISTED.value:
            move(db, c, Stage.AI_INTERVIEW, RECRUITER, reason)
    db.commit()
    return chosen


def main() -> int:
    init_db()
    with SessionLocal() as db:
        req = db.scalars(select(Requisition).where(Requisition.title.ilike("%cloud support%"))).first() or db.scalars(select(Requisition)).first()
        if req is None or req.status not in ("APPROVED", "PUBLISHED"):
            print("There is no approved Cloud Support Engineer job. Run: python -m scripts.day1_demo")
            return 1
        cands = free_candidates(db, req, len(PERSONAS))
        if len(cands) < len(PERSONAS):
            print(f"Only {len(cands)} candidate(s) are free for a sample interview; run python -m scripts.day1_demo first so there are enough.")
            return 1
        print(f"Making {len(PERSONAS)} sample interviews for {req.title} (the voices take a moment) ...\n")
        for cand, persona in zip(cands, PERSONAS):
            res = run_interview(db, cand, req, persona, PROFILES[persona], speak=True)
            card = res["scorecard"]
            s = db.query(InterviewSession).filter_by(candidate_id=cand.id).one()
            db.add(DecisionLog(actor="system", action="sample interview built", subject=f"interview:{s.id}",
                               reason=f"SAMPLE: fictional candidate ({persona}); simulated answers, two different voices"))
            db.commit()
            scored = [a["score"] for a in card["answers"] if not a["skipped"]]
            print(f"  {persona:<10} candidate #{cand.id}  interview {s.id}  questions {len(card['answers'])}  average {sum(scored) / max(1, len(scored)):.2f} / 3  "
                  f"scorer disagreements {len(card['disagreements'])}")
            print(f"             recording: {mp3_path(s)}")
        print("\nOpen /interviews as the recruiter: each one is labelled SAMPLE: fictional candidate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
