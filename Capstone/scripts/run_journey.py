"""The whole journey for REQ-014 in one command (Day 4, BR-15): voice note -> rubric -> 52 CVs -> shortlist -> AI interview -> human interview -> decision.

    python -m scripts.run_journey --reset        (wipes data/ and storage/ first, then runs: for a clean demo)
    python -m scripts.run_journey --quiet        (less output, used by the Docker container)

Every approval is made by a person: the hiring manager (hm@example.com) approves the rubric; the recruiter (recruiter@example.com) checks the unsure
fields, approves the shortlist, invites candidates, approves every email, reviews every scorecard and makes every decision. The script plays those
two people through the real web pages. Everything uses fake models and fictional data. Afterwards: uvicorn app.main:app --port 8001
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.agents.compliance import review
from app.config import get_settings
from app.db import SessionLocal, engine, init_db
from app.main import app
from app.models import Candidate, DecisionLog, Requisition, ReviewItem
from app.models_ext import EmailDraft, ExplanationRequest, FinalDecision, HumanInterview, InterviewSession, ItemScoreRow, OutboxLog, ShortlistEntry
from scripts.create_users import DEMO_PASSWORD, create_users
from scripts.upload_cvs import DEFAULT_FOLDER, upload_all

KIT = Path("starter_kit")
RECORDED = {"C-001_cv.pdf": "strong", "C-002_cv.pdf": "weak", "C-011_cv.docx": "cv_conflict", "C-004_cv.docx": "forbidden_question"}  # the four recorded human interviews
DECISIONS = {
    "C-001_cv.pdf": ("ADVANCE", "Strong evidence in the CV and in both interviews; clear on networking and incident handling."),
    "C-002_cv.pdf": ("NOT_THIS_TIME", "Gaps in networking and incident handling in both rounds; a better fit for a more junior role."),
    "C-011_cv.docx": ("HOLD", "Strong technical answers, but the Kubernetes experience needs clarifying before we go further."),
    "C-004_cv.docx": ("ADVANCE", "Strong technical answers. The question about children should not have been asked and was not used in scoring."),
}


def reset() -> None:
    engine.dispose()
    s = get_settings()
    for url in (s.database_url, s.ops_database_url):
        if url.startswith("sqlite:///"):
            for suffix in ("", "-wal", "-shm"):
                Path(url.replace("sqlite:///", "", 1) + suffix).unlink(missing_ok=True)
    shutil.rmtree(s.storage_dir, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    say = (lambda *a: None) if args.quiet else print
    if args.reset:
        reset()
        say("Reset: removed the databases and storage folder.")
    init_db()
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Requisition)):
            print("The database already has data. Run again with --reset to start from an empty one.")
            return 1
        create_users(db)
    log: list[str] = []

    def step(n: int, text: str) -> None:
        log.append(f"{n}. {text}")
        say(f"{n}. {text}")

    with TestClient(app, follow_redirects=False) as hm, TestClient(app, follow_redirects=False) as rc, TestClient(app, follow_redirects=False) as visitor:
        hm.post("/login", data={"email": "hm@example.com", "password": DEMO_PASSWORD})
        rc.post("/login", data={"email": "recruiter@example.com", "password": DEMO_PASSWORD})

        step(1, "Hiring manager uploads the voice note; the requisition agent writes the job description and rubric; wording is checked; the hiring manager approves and publishes")
        note = KIT / "voice_notes" / "REQ_cloud_support_engineer.wav"
        hm.post("/requisitions", data={"title": "Cloud Support Engineer"}, files={"audio": (note.name, note.read_bytes(), "audio/wav")})
        hm.post("/requisitions/1/generate")
        hm.post("/requisitions/1/approve", data={"comment": "Checked against my voice note; the biased phrases were not carried into the job text"})
        hm.post("/requisitions/1/publish")

        step(2, "52 candidates apply (PDF, Word, scans, screenshots); the document agent reads each CV; identity is hidden; unsure fields go to the review queue")
        accepted, refused = upload_all(visitor, 1, DEFAULT_FOLDER)
        with SessionLocal() as db:
            ids = {c.cv_name: c.id for c in db.scalars(select(Candidate))}
            review_ids = [c.id for c in db.scalars(select(Candidate).where(Candidate.stage == "REVIEW"))]
            pending = {i: [(r.field, r.value) for r in db.scalars(select(ReviewItem).where(ReviewItem.candidate_id == i, ReviewItem.resolved.is_(False)))] for i in review_ids}

        step(3, f"The recruiter checks {len(review_ids)} scanned CVs against the originals and confirms the fields")
        for cid, items in pending.items():
            rc.post(f"/review/{cid}/save", data={f"value_{f}": v for f, v in items})
            rc.post(f"/review/{cid}/confirm")

        step(4, "The screening agent scores every candidate 0-3 on every skill with an exact CV quote; the compliance reviewer checks every quote; a shortlist is suggested")
        rc.post("/screening/1/run")
        with SessionLocal() as db:
            suggested = [e.candidate_id for e in db.scalars(select(ShortlistEntry).where(ShortlistEntry.status == "SUGGESTED").order_by(ShortlistEntry.rank))]
        recorded_ids = [ids[f] for f in RECORDED]
        chosen = suggested + [i for i in recorded_ids if i not in suggested]

        step(5, f"The recruiter approves the shortlist: the top {len(suggested)} plus {len(chosen) - len(suggested)} added to follow the recorded interviews (a person decides)")
        rc.post("/screening/1/approve", data={"reason": "Top five by verified evidence, plus the candidates whose recorded interviews we will review", "candidate_id": chosen})

        step(6, "The recruiter invites the shortlist to the AI interview and approves the invitations in the outbox; one candidate asks for a person instead")
        asked_for_person = ids["C-002_cv.pdf"]
        for cid in chosen:
            rc.post(f"/interviews/{cid}/invite", data={"reason": "strongest evidence on the must-have skills; invited to the first-round AI interview"})
        with SessionLocal() as db:
            drafts = [d.id for d in db.scalars(select(EmailDraft).where(EmailDraft.status == "DRAFT", EmailDraft.kind == "ai_interview"))]
            tokens = {c.id: c.access_token for c in db.scalars(select(Candidate))}
        for d in drafts:
            rc.post(f"/outbox/{d}/approve")
        visitor.post(f"/interview/{tokens[asked_for_person]}/person")

        step(7, "AI interviews run from recorded answers (spoken questions, diagrams, follow-ups); each answer is scored with a quote; the recruiter reviews every scorecard")
        for cid in chosen:
            if cid == asked_for_person:
                continue
            quality = "strong" if cid in suggested else "partial"
            rc.post(f"/interviews/{cid}/replay", data={"quality": quality})
            rc.post(f"/interviews/{cid}/review")

        step(8, "Second round: the recruiter moves four candidates to a human interview; the copilot follows each recording live; the recruiter scores")
        for f in RECORDED:
            cid = ids[f]
            rc.post(f"/copilot/{cid}/to-human-interview")
            rc.post(f"/copilot/{cid}/ack")
            r = rc.get(f"/copilot/{cid}/events", params={"speed": 0})
            draft = None
            for block in r.text.strip().split("\n\n"):
                ev, data = block.split("\n", 1)
                if ev == "event: draft":
                    draft = json.loads(data[len("data: "):])
            scores = {f"score_{a['question_id']}": a["suggested_score"] for a in (draft or {"answers": []})["answers"] if a["type"] == "technical"}
            rc.post(f"/copilot/{cid}/scores", data={**scores, "note": "Scores follow what I heard; the copilot's draft agreed"})
        with SessionLocal() as db:
            inv = [d.id for d in db.scalars(select(EmailDraft).where(EmailDraft.status == "DRAFT", EmailDraft.kind == "invitation"))]
        for d in inv:
            rc.post(f"/outbox/{d}/approve")

        step(9, "The recruiter decides on each interviewed candidate, with a reason; the decision emails are drafted and approved")
        for f, (decision, reason) in DECISIONS.items():
            rc.post(f"/scorecard/{ids[f]}/decide", data={"decision": decision, "reason": reason})
        with SessionLocal() as db:
            dec = [d.id for d in db.scalars(select(EmailDraft).where(EmailDraft.status == "DRAFT", EmailDraft.kind == "decision"))]
        for d in dec:
            rc.post(f"/outbox/{d}/approve")

        step(10, "A candidate who was not shortlisted asks why; an explanation is drafted from the evidence; the recruiter reviews and approves it")
        with SessionLocal() as db:
            not_shortlisted = db.scalars(select(Candidate).where(Candidate.stage == "SCREENED", Candidate.requisition_id == 1).order_by(Candidate.id)).first()
        if not_shortlisted:
            visitor.post(f"/me/{not_shortlisted.access_token}/explain")
            with SessionLocal() as db:
                ex = db.scalars(select(ExplanationRequest)).first()
            if ex and ex.draft_id:
                rc.post(f"/outbox/{ex.draft_id}/approve")

        step(11, "Final checks: the compliance reviewer re-checks everything; the decision log is checked for any decision, message or move without a person")
        with SessionLocal() as db:
            new = review(db)
            from app.agents.compliance import ComplianceAgent
            without_person = ComplianceAgent(db).call("check_log")
            summary = {
                "candidates": db.query(Candidate).count(), "stages": {s: n for s, n in db.execute(select(Candidate.stage, func.count(Candidate.id)).group_by(Candidate.stage)).all()},
                "scores_with_verified_quote": f"{sum(1 for r in db.scalars(select(ItemScoreRow)) if r.score > 0 and r.verified)}/{sum(1 for r in db.scalars(select(ItemScoreRow)) if r.score > 0)}",
                "ai_interviews_done": db.query(InterviewSession).filter_by(status="DONE").count(),
                "asked_for_a_person": db.query(InterviewSession).filter_by(status="PERSON_REQUESTED").count(),
                "copilot_interviews": db.query(HumanInterview).filter_by(status="DONE").count(),
                "final_decisions": [(d.decision, d.actor) for d in db.scalars(select(FinalDecision))],
                "emails_sent_after_approval": db.query(OutboxLog).count(), "emails_waiting": db.query(EmailDraft).filter_by(status="DRAFT").count(),
                "decision_log_entries": db.query(DecisionLog).count(),
                "decisions_messages_or_moves_without_a_person": len(without_person), "new_compliance_findings": len(new),
                "applications_accepted": accepted, "applications_refused": refused,
            }
            from mcp_server import tracking
            tracking.export_from_app(db, get_settings().storage_dir / "tracking_system.db")
    Path("evidence").mkdir(exist_ok=True)
    Path("evidence/journey.json").write_text(json.dumps({"steps": log, "summary": summary}, indent=1, default=str), encoding="utf-8")
    print()
    print(f"REQ-014 journey complete: {summary['candidates']} candidates, stages {summary['stages']}")
    print(f"  {summary['scores_with_verified_quote']} scores with a verified quote; {summary['ai_interviews_done']} AI interviews ({summary['asked_for_a_person']} asked for a person); "
          f"{summary['copilot_interviews']} copilot-followed human interviews")
    print(f"  decisions: {[d for d, _ in summary['final_decisions']]} (all by {sorted({a for _, a in summary['final_decisions']})})")
    print(f"  emails: {summary['emails_sent_after_approval']} sent after a person approved, {summary['emails_waiting']} still waiting; nothing sent without approval")
    print(f"  decisions, messages or moves without a person: {summary['decisions_messages_or_moves_without_a_person']}; decision log entries: {summary['decision_log_entries']}")
    ok = summary["decisions_messages_or_moves_without_a_person"] == 0 and refused == 0 and len(summary["final_decisions"]) == 4
    print("JOURNEY OK" if ok else "JOURNEY FINISHED WITH PROBLEMS: see above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
