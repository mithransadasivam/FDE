"""Runs the whole of Day 3 in one command, in fake mode, and prints what it did (Day 3, end of day).

    python -m scripts.day3_demo

It runs the security scan and the attack suite, runs the evidence checker on all screenings, makes a practice recruiter interview for one shortlisted candidate, runs a
copilot session on it at 4x speed, and prints: security flags, attack results, checker results, the transcript lines, warnings with their timing, suggestions, points
heard, CV conflict cards, the recruiter scoring page link, the outbox drafts, and the replay link for a sample interview. All data is fictional. Nothing is pushed or sent.

It needs the data of Days 1 and 2 (python -m scripts.day1_demo, then python -m scripts.day2_demo); if the database is empty it runs them first.
"""
import os
import subprocess
import sys

os.environ.setdefault("FAKE_MODELS", "1")

from sqlalchemy import func, select  # noqa: E402

from app.agents.checker import run_checks  # noqa: E402
from app.agents.copilot import CopilotAgent  # noqa: E402
from app.agents.screening import screen_requisition  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.interview.recording import json_path  # noqa: E402
from app.models import Candidate, Requisition  # noqa: E402
from app.models_ext import EmailDraft, EvidenceCheck, Flag, HumanInterview, InterviewSession  # noqa: E402
from app.practice import make_practice  # noqa: E402
from app.shortlist import suggest_shortlist  # noqa: E402
from app.voice.replayer import replay  # noqa: E402


def line(title: str) -> None:
    print(f"\n=== {title} " + "=" * max(3, 70 - len(title)))


def main() -> int:
    if not get_settings().fake_models:
        print("Day 3's demo runs in fake mode: set FAKE_MODELS=1.")
        return 1
    init_db()
    with SessionLocal() as db:
        empty = not db.scalar(select(func.count()).select_from(Requisition))
        no_interviews = not db.scalar(select(func.count()).select_from(InterviewSession).where(InterviewSession.status == "DONE"))
    if empty and subprocess.run([sys.executable, "-m", "scripts.day1_demo"]).returncode != 0:
        return 1
    if empty or no_interviews:
        print("Running the Day 2 demo first (it makes the shortlist and two sample interviews) ...")
        if subprocess.run([sys.executable, "-m", "scripts.day2_demo"], stdout=subprocess.DEVNULL).returncode != 0:
            return 1

    line("1. Security scan: hidden and planted instructions in CVs")
    scan = subprocess.run([sys.executable, "-m", "scripts.security_scan", "--save"], capture_output=True, text=True)
    print("\n".join(ln for ln in scan.stdout.splitlines() if ln.strip() and "INFO" not in ln and "WARNING" not in ln))
    with SessionLocal() as db:
        flags = db.scalars(select(Flag).where(Flag.kind.in_(["hidden text in CV", "instructions in CV ignored"]))).all()
        print(f"Security flags on record: {len(flags)} (nothing was rejected: a person decides)")

    line("2. The attack suite (gullible fake models: any order outside the data markers is obeyed)")
    done = subprocess.run([sys.executable, "-m", "pytest", "tests/test_attacks.py", "-q", "-s", "-p", "no:cacheprovider"], capture_output=True, text=True)
    table = [ln for ln in done.stdout.splitlines() if ln.startswith(("attack", "-----", "cv-", "spoken-", "email-"))]
    print("\n".join(table) or done.stdout[-800:])

    line("3. The evidence checker on every screening")
    with SessionLocal() as db:
        req = db.scalars(select(Requisition).where(Requisition.title.ilike("%cloud support%"))).first()
        if db.scalar(select(func.count()).select_from(Candidate).where(Candidate.stage == "EXTRACTED", Candidate.requisition_id == req.id)):
            screen_requisition(db, req.id, "recruiter@example.com")
            suggest_shortlist(db, req.id)
        needs = run_checks(db, req.id)
        rows = db.scalars(select(EvidenceCheck).where(EvidenceCheck.subject == "screening")).all()
        print(f"Checked {len(rows)} screenings: {sum(1 for r in rows if r.status == 'CHECKED')} CHECKED, {needs} NEEDS_REVIEW. The checker reports; it never changes a score.")
        for r in [r for r in rows if r.status == "NEEDS_REVIEW"][:3]:
            print(f"  candidate {r.candidate_id}: " + "; ".join(f"{p['where']}: {p['problem']}" for p in r["items"][:2] if isinstance(p, dict)) if False else f"  candidate {r.candidate_id}: {len(r.items or [])} problem(s)")

        line("4. A practice recruiter interview (SAMPLE: fictional) for one shortlisted candidate")
        cand = db.scalars(select(Candidate).where(Candidate.requisition_id == req.id, Candidate.stage.in_(["SHORTLISTED", "AI_INTERVIEW"])).order_by(Candidate.id)).first()
        if cand is None:
            print("No shortlisted candidate: run python -m scripts.day2_demo first.")
            return 1
        doc = make_practice(db, cand, speak_real=False)
        print(f"Candidate #{cand.id}: {len(doc['lines'])} lines, {doc['duration_s']} s, storage/practice/{cand.id}/practice.json")
        for m, info in doc["moments"].items():
            print(f"  planned moment {m:<22} line {info['line']:>2} at {info['start']:>5.1f}s")

        line("5. A copilot session on it at 4x speed")
        agent = CopilotAgent(db, cand, db.get(Requisition, cand.requisition_id))
        events = []
        for turn in replay(doc, 0.0):  # (4x speed would only add waiting: the timings printed are the recording's own)
            events += agent.process_turn(turn["speaker"], turn["text"], turn["start"], turn["end"])
        print("Transcript:")
        for e in [e for e in events if e.kind == "transcript"]:
            print(f"  {e.data['speaker'][:4].upper():<5} {e.t:>6.1f}s  {e.data['text'][:88]}")
        print("\nWarnings (forbidden questions), with timing:")
        for w in agent.warnings:
            print(f"  warned {w['lag_s'] * 1000:.1f} ms after the question ended: \"{w['question']}\" -> try: \"{w['better_question']}\"; the answer was not used for scoring")
        print("\nSuggestions (one technical, one behavioural), after the last answer:")
        for s in [e for e in events if e.kind == "suggestion"][-1:]:
            for item in s.data["items"]:
                print(f"  [{item['kind_group']}] {item['skill']}: \"{item['text'][:70]}\"  (why: {item['why'][:50]})")
                for p in item["points"][:3]:
                    print(f"        - {p}")
        print("\nPoints heard:")
        for qid, pts in agent.ticked.items():
            total = len(agent.bank[qid].get("key_points") or [1, 2, 3, 4])
            print(f"  {qid} {agent.bank[qid]['skill']}: {len(pts)} of {total}")
        print("\nCV conflict cards:")
        for c in agent.conflicts:
            print(f"  said: \"{c.get('said', c['text'])[:70]}\"  |  CV: {c.get('cv', '')[:60]}  |  ask: {c.get('question', '')[:70]}")
        row = HumanInterview(candidate_id=cand.id, recording=doc["file"], notice_ack=True, status="DONE", source="practice", events=[e.model_dump() for e in agent.events],
                             draft_scorecard=agent.draft_scorecard(), lines=doc["turns"])
        db.add(row)
        db.commit()

        line("6. Where the recruiter scores it, and the drafts and replay")
        print(f"  Recruiter scoring page: /copilot/{cand.id}   (the recruiter enters their own levels, then decides with a reason)")
        drafts = db.scalars(select(EmailDraft).where(EmailDraft.status == "DRAFT")).all()
        print(f"  Outbox: {len(drafts)} draft(s) waiting for a person to approve; nothing is sent without one")
        for d in drafts[:4]:
            print(f"    #{d.id} {d.kind}: {d.subject}")
        sample = db.scalars(select(InterviewSession).where(InterviewSession.sample.is_(True), InterviewSession.status == "DONE")).first()
        if sample:
            ready = json_path(sample).exists()
            print(f"  Replay room for sample interview {sample.id}: /interviews/{sample.id}/replay   ({'ready once the recruiter has entered their own levels' if ready else 'recording not built'})")
    print("\nDay 3 demo complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
