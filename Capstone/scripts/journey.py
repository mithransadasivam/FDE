"""The whole journey in one command (Day 4, prompt 7): voice note to decision, end to end, with the time every step takes.

    python -m scripts.journey --fake      fictional data, fake models, no key needed (about a minute or two)
    python -m scripts.journey --real      the same journey with the real models (needs OPENROUTER_API_KEY in .env; costs a little)

It starts from an EMPTY database of its own (data/journey.db, data/journey_ops.db and data/journey_storage/), so it never touches the app's data, and it can be run again at
any time: the old run is deleted first. It plays the hiring manager and the recruiter through the same web pages the app uses (no shortcuts): every step that a person
would do in real use is marked "ON A PERSON'S BEHALF" in the report, with the person's role. Where the script stands in for a person it says what the person would do.

Prints each step's result and time, the total cost, and the links to open in the app. Writes reports/journey.md and reports/journey.json.
"""
import argparse
import contextlib
import io
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DATA = Path("data")
ARGS = argparse.ArgumentParser()
ARGS.add_argument("--fake", action="store_true")
ARGS.add_argument("--real", action="store_true")
ARGS.add_argument("--keep", action="store_true", help="do not delete the previous journey database first")
OPTS, _ = ARGS.parse_known_args()
REAL = OPTS.real and not OPTS.fake
if REAL and not (os.environ.get("OPENROUTER_API_KEY") or any("OPENROUTER_API_KEY" in l and "=" in l and l.split("=", 1)[1].strip() for l in
                                                           (Path(".env").read_text(encoding="utf-8").splitlines() if Path(".env").exists() else []))):
    print("--real needs OPENROUTER_API_KEY (in the environment or in .env). Run with --fake for the fictional, no-key journey.")
    sys.exit(2)
os.environ["FAKE_MODELS"] = "0" if REAL else "1"
os.environ["DATABASE_URL"] = f"sqlite:///{(DATA / 'journey.db').as_posix()}"
os.environ["OPS_DATABASE_URL"] = f"sqlite:///{(DATA / 'journey_ops.db').as_posix()}"
os.environ["STORAGE_DIR"] = str(DATA / "journey_storage")

import shutil  # noqa: E402

DATA.mkdir(exist_ok=True)
if not OPTS.keep:
    for suffix in ("", "-wal", "-shm"):
        for name in ("journey.db", "journey_ops.db"):
            (DATA / f"{name}{suffix}").unlink(missing_ok=True)
    shutil.rmtree(DATA / "journey_storage", ignore_errors=True)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app import costing  # noqa: E402
from app.agents.checker import run_checks  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.interview import recording  # noqa: E402
from app.interview.bank import core_questions, load_questions  # noqa: E402
from app.interview.scorecard import build_card  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Candidate, DecisionLog, Requisition, ReviewItem  # noqa: E402
from app.models_ext import EmailDraft, EvidenceCheck, FinalDecision, Flag, HumanInterview, InterviewSession, ItemScoreRow, ShortlistEntry  # noqa: E402
from app.practice import make_practice  # noqa: E402
from evals.common import table, write_report  # noqa: E402
from scripts.create_users import DEMO_PASSWORD, create_users  # noqa: E402
from scripts.upload_cvs import DEFAULT_FOLDER, upload_all  # noqa: E402

KIT = Path("starter_kit")
HM_BEHALF = "ON A PERSON'S BEHALF: hiring manager"
RC_BEHALF = "ON A PERSON'S BEHALF: recruiter"


class Journey:
    def __init__(self):
        self.rows: list[dict] = []
        self.state: dict = {}
        self.started = time.perf_counter()

    def run(self, name: str, who: str, fn, needs: tuple[str, ...] = ()) -> None:
        failed = [n for n in needs if any(r["name"] == n and r["status"] != "OK" for r in self.rows)]
        if failed:
            self.rows.append({"n": len(self.rows) + 1, "name": name, "who": who, "status": "SKIPPED", "seconds": 0.0, "result": f"needs '{failed[0]}', which did not finish"})
            print(f"  {len(self.rows):>2}. SKIPPED  {name} (needs '{failed[0]}')")
            return
        t0 = time.perf_counter()
        try:
            result = fn() or ""
            status = "OK"
        except Exception as e:  # say what was being done when it failed, then carry on with whatever does not depend on it
            status, result = "FAILED", f"while doing this step: {type(e).__name__}: {str(e)[:300]}"
        seconds = round(time.perf_counter() - t0, 2)
        self.rows.append({"n": len(self.rows) + 1, "name": name, "who": who, "status": status, "seconds": seconds, "result": result})
        print(f"  {len(self.rows):>2}. {status:<8} {seconds:>6.2f}s  {name}" + (f"  ({result})" if result and status == "OK" else ""))
        if status != "OK":
            print(f"      {result}")


def approve_drafts(rc, kind: str | None = None) -> int:
    with SessionLocal() as db:
        ids = [d.id for d in db.scalars(select(EmailDraft).where(EmailDraft.status == "DRAFT", *( [EmailDraft.kind == kind] if kind else [])))]
    for i in ids:
        rc.post(f"/outbox/{i}/approve")
    return len(ids)


def main() -> int:
    mode = "real models" if REAL else "fake models (fictional data)"
    print(f"Journey ({mode}): a fresh database in data/journey.db\n")
    init_db()
    with SessionLocal() as db:
        create_users(db)
    j = Journey()
    S = j.state
    with TestClient(app, follow_redirects=False) as hm, TestClient(app, follow_redirects=False) as rc, TestClient(app, follow_redirects=False) as visitor:
        hm.post("/login", data={"email": "hm@example.com", "password": DEMO_PASSWORD})
        rc.post("/login", data={"email": "recruiter@example.com", "password": DEMO_PASSWORD})

        def upload_note():
            note = KIT / "voice_notes" / "REQ_cloud_support_engineer.wav"
            r = hm.post("/requisitions", data={"title": "Cloud Support Engineer"}, files={"audio": (note.name, note.read_bytes(), "audio/wav")})
            assert r.status_code in (200, 303), f"upload answered {r.status_code}"
            return f"{note.name} uploaded"

        def generate_and_approve():
            hm.post("/requisitions/1/generate")
            with SessionLocal() as db:
                req = db.get(Requisition, 1)
                assert req.rubric and req.job, "no job description or rubric was written"
                S["skills"] = [i["skill"] for i in req.rubric["items"]]
                flags = len(req.wording_flags or [])
            hm.post("/requisitions/1/approve", data={"comment": "Checked against my voice note; the biased phrases were not carried into the job text"})
            with SessionLocal() as db:
                assert db.get(Requisition, 1).status in ("APPROVED", "PUBLISHED"), "the approval was not recorded"
            return f"{len(S['skills'])} rubric skills, {flags} wording flag(s), approved with a reason"

        def publish():
            hm.post("/requisitions/1/publish")
            with SessionLocal() as db:
                assert db.get(Requisition, 1).status == "PUBLISHED"
            assert visitor.get("/jobs/1").status_code == 200
            return "the job page is public"

        def upload_cvs():
            accepted, refused = upload_all(visitor, 1, DEFAULT_FOLDER)
            assert refused == 0 and accepted == 52, f"{accepted} accepted, {refused} refused"
            with SessionLocal() as db:
                S["ids"] = {c.cv_name: c.id for c in db.scalars(select(Candidate))}
                S["review"] = [c.id for c in db.scalars(select(Candidate).where(Candidate.stage == "REVIEW"))]
            return f"{accepted} CVs read; {len(S['review'])} sent to the review queue"

        def review_queue():
            for cid in S["review"]:
                with SessionLocal() as db:
                    items = [(r.field, r.value) for r in db.scalars(select(ReviewItem).where(ReviewItem.candidate_id == cid, ReviewItem.resolved.is_(False)))]
                rc.post(f"/review/{cid}/save", data={f"value_{f}": v for f, v in items})
                rc.post(f"/review/{cid}/confirm")
            with SessionLocal() as db:
                db.add(DecisionLog(actor="journey script", action="review queue confirmed by the script", subject="requisition:1",
                                   reason=f"{len(S['review'])} CV(s) were confirmed as read by the extractor. In real use a recruiter checks every unsure field against the original CV; "
                                          "this script stands in for that person so the journey can run."))
                db.commit()
                left = db.scalar(select(func.count()).select_from(ReviewItem).where(ReviewItem.resolved.is_(False)))
            assert left == 0, f"{left} review items are still open"
            return f"{len(S['review'])} CV(s) confirmed; the log notes that a person would do this"

        def security_scan():
            from scripts import security_scan as ss

            sys.argv = ["security_scan", "--save"]
            with contextlib.redirect_stdout(io.StringIO()):
                ss.main()
            with SessionLocal() as db:
                n = db.scalar(select(func.count()).select_from(Flag).where(Flag.kind.in_(["hidden text in CV", "instructions in CV ignored"])))
            assert n >= 1, "the planted instruction in the starter kit was not found"
            return f"{n} hidden or planted instruction(s) found and flagged for a person; nothing was rejected"

        def screening_and_checker():
            rc.post("/screening/1/run")
            with SessionLocal() as db:
                needs = run_checks(db, 1)
                db.commit()
                scored = db.scalar(select(func.count(func.distinct(ItemScoreRow.candidate_id))))
                bad = db.scalar(select(func.count()).select_from(ItemScoreRow).where(ItemScoreRow.score > 0, ItemScoreRow.verified.is_(False)))
                S["checks"] = [c.id for c in db.scalars(select(EvidenceCheck).where(EvidenceCheck.status == "NEEDS_REVIEW", EvidenceCheck.acknowledged_by.is_(None)))]
            assert scored >= 40 and bad == 0, f"{scored} candidates scored; {bad} score(s) without a verified quote"
            return f"{scored} candidates scored, every quote verified, {needs} checker item(s) for a person"

        def shortlist():
            for cid in S["checks"]:
                rc.post(f"/screening/checks/{cid}/ack", data={"note": "read by the script on the recruiter's behalf"})
            with SessionLocal() as db:
                top = [e.candidate_id for e in db.scalars(select(ShortlistEntry).where(ShortlistEntry.status == "SUGGESTED").order_by(ShortlistEntry.rank))][:6]
                if len(top) < 6:  # the suggestion is shorter than six: fill from the best CV totals
                    totals: dict[int, float] = {}
                    for r in db.scalars(select(ItemScoreRow)):
                        totals[r.candidate_id] = totals.get(r.candidate_id, 0) + r.weight * r.score / 3
                    top += [c for c, _ in sorted(totals.items(), key=lambda kv: -kv[1]) if c not in top][:6 - len(top)]
            r = rc.post("/screening/1/approve", data={"reason": "The six strongest by verified evidence on the must-have skills", "candidate_id": top})
            with SessionLocal() as db:
                got = db.scalar(select(func.count()).select_from(Candidate).where(Candidate.stage == "SHORTLISTED"))
            assert got == 6, f"{got} candidate(s) shortlisted"
            S["shortlist"] = top
            return f"top 6 shortlisted with a reason: {top}"

        def scoring_scale():
            bank = load_questions()
            with SessionLocal() as db:
                items = db.get(Requisition, 1).rubric["items"]
            have = [i["skill"] for i in items if any(q["skill"].lower() == i["skill"].lower() and q.get("scoring") for q in bank.values())]
            core = core_questions(items)
            assert have and all((q.get("scoring") or {}).get("0") is not None for q in core), "a core question has no 0-3 scale"
            with SessionLocal() as db:
                db.add(DecisionLog(actor="journey script", action="scoring scale checked by the script", subject="requisition:1",
                                   reason=f"{len(core)} core questions each have a described 0-3 scale; in real use a recruiter reads the scale before inviting anyone"))
                db.commit()
            return f"{len(core)} core questions have a described 0-3 scale ({len(have)} of {len(items)} rubric skills have questions with scales)"

        def invite_two():
            strong, weak = S["shortlist"][0], S["shortlist"][-1]
            S["strong"], S["weak"] = strong, weak
            for cid in (strong, weak):
                r = rc.post(f"/interviews/{cid}/invite", data={"reason": "Strong evidence on the must-have skills; invited to the first-round AI interview"})
                assert r.status_code == 303, f"the invitation answered {r.status_code}"
            n = approve_drafts(rc, "ai_interview")
            assert n == 2, f"{n} invitation email(s) approved"
            return f"candidates {strong} and {weak} invited; both invitation emails approved"

        def ai_interviews():
            from tests.sim.runner import run_interview  # the simulated candidates (strong, weak, off-topic, trickster) answer through the same functions the interview page uses

            with SessionLocal() as db:
                req = db.get(Requisition, 1)
                for cid, persona in ((S["strong"], "strong"), (S["weak"], "weak")):
                    run_interview(db, db.get(Candidate, cid), req, persona)
            with SessionLocal() as db:
                done = db.scalar(select(func.count()).select_from(InterviewSession).where(InterviewSession.status == "DONE"))
                strong = build_card(db, db.query(InterviewSession).filter_by(candidate_id=S["strong"]).one())["overall_100"]
                weak = build_card(db, db.query(InterviewSession).filter_by(candidate_id=S["weak"]).one())["overall_100"]
            assert done == 2 and strong > weak, f"{done} interviews done; strong {strong}, weak {weak}"
            return f"strong simulated candidate {strong}/100, weak simulated candidate {weak}/100"

        def recordings():
            with SessionLocal() as db:
                for cid in (S["strong"], S["weak"]):
                    s = db.query(InterviewSession).filter_by(candidate_id=cid).one()
                    assert recording.mp3_path(s).exists() and recording.json_path(s).exists(), f"no recording for candidate {cid}"
                    card = build_card(db, s)
                    levels = {f"level_{n}": r["level"] if r["level"] is not None else 0 for n, r in enumerate(card["skills"]) if r["must_have"]}
                    rc.post(f"/interviews/{cid}/review", data={**levels, "note": "Entered by the script on the recruiter's behalf, from the AI's own levels"})
                    db.expire_all()
                    assert db.query(InterviewSession).filter_by(candidate_id=cid).one().review, f"the review of candidate {cid} was not saved"
            assert rc.get(f"/interviews/{S['strong']}/replay").status_code == 200
            return "full_conversation.mp3 and recording.json for both; the replay room opens after the recruiter's own levels"

        def practice_and_copilot():
            cid = S["strong"]
            with SessionLocal() as db:
                make_practice(db, db.get(Candidate, cid), speak_real=False)
            rc.post(f"/copilot/{cid}/to-human-interview")
            rc.post(f"/copilot/{cid}/ack")
            r = rc.get(f"/copilot/{cid}/events", params={"speed": 0})
            import json

            draft, warnings = None, 0
            for block in r.text.strip().split("\n\n"):
                ev, data = block.split("\n", 1)
                if ev == "event: copilot":
                    warnings += json.loads(data[len("data: "):])["kind"] == "warning"
                elif ev == "event: draft":
                    draft = json.loads(data[len("data: "):])
            assert draft and warnings >= 1, "the copilot made no draft or caught no forbidden question"
            S["draft"] = draft
            return f"practice interview followed by the copilot: {warnings} forbidden-question warning(s), {len(draft['cv_checks'])} CV check(s)"

        def scores_and_decision():
            cid = S["strong"]
            tech = [a for a in S["draft"]["answers"] if a["type"] == "technical"]
            scores = {f"score_{a['question_id']}": a["suggested_score"] or 0 for a in tech}  # a person reads the transcript and enters a level; here it agrees with the draft
            reasons = {f"reason_{a['question_id']}": "entered by the script on the recruiter's behalf; the recruiter would read the transcript first" for a in tech}
            rc.post(f"/copilot/{cid}/scores", data={**scores, **reasons, "note": "My own levels, after reading the transcript; the copilot's draft was a suggestion"})
            with SessionLocal() as db:
                pending = [c.id for c in db.scalars(select(EvidenceCheck).where(EvidenceCheck.candidate_id == cid, EvidenceCheck.status == "NEEDS_REVIEW", EvidenceCheck.acknowledged_by.is_(None)))]
            for p in pending:
                rc.post(f"/screening/checks/{p}/ack", data={"note": "read by the script on the recruiter's behalf"})
            rc.post(f"/scorecard/{cid}/decide", data={"decision": "ADVANCE", "reason": "Strong evidence in the CV and in both interviews; the question about family was not used."})
            rc.post(f"/interviews/{S['weak']}/decision", data={"decision": "withdraw", "reason": "Gaps in the must-have skills in the first round; a better fit for a more junior role."})
            with SessionLocal() as db:
                d = db.query(FinalDecision).filter_by(candidate_id=cid).one_or_none()
                assert d and d.actor == "recruiter@example.com", "no decision by a person was recorded"
                hi = db.query(HumanInterview).filter_by(candidate_id=cid).one()
                assert hi.recruiter_scores, "the recruiter's own scores were not saved"
            return f"recruiter scored and decided {d.decision} with a reason; the weak candidate was withdrawn with a reason"

        def emails():
            n = approve_drafts(rc)
            with SessionLocal() as db:
                waiting = db.scalar(select(func.count()).select_from(EmailDraft).where(EmailDraft.status == "DRAFT"))
            assert waiting == 0, f"{waiting} email(s) still waiting"
            return f"{n} more email(s) approved by the recruiter; nothing is sent without a person"

        def scorecard():
            cid = S["strong"]
            r = rc.get(f"/candidates/{cid}/scorecard")
            assert r.status_code == 200 and "The three stages side by side" in r.text, "the scorecard did not open"
            assert "play this moment" in r.text, "no 'play this moment' link on the scorecard"
            blind = hm.get(f"/candidates/{cid}/scorecard").text
            with SessionLocal() as db:
                name = db.get(Candidate, cid).profile["name"]["value"]
            assert name not in blind, "the hiring manager's scorecard shows the candidate's name"
            return "all three stages side by side; play links work; the hiring manager's view is blind"

        steps = [
            ("Upload the starter-kit voice note", HM_BEHALF, upload_note, ()),
            ("Generate and approve the job and rubric (with a reason)", HM_BEHALF, generate_and_approve, ("Upload the starter-kit voice note",)),
            ("Publish the job", HM_BEHALF, publish, ("Generate and approve the job and rubric (with a reason)",)),
            ("Upload the 52 CVs (candidates apply; CVs are read and blinded)", "candidates (public page)", upload_cvs, ("Publish the job",)),
            ("Review queue confirmed (a person would do this: logged)", RC_BEHALF, review_queue, ("Upload the 52 CVs (candidates apply; CVs are read and blinded)",)),
            ("Security scan: hidden and planted instructions", "code", security_scan, ("Upload the 52 CVs (candidates apply; CVs are read and blinded)",)),
            ("Screening and the evidence checker", "AI + code", screening_and_checker, ("Review queue confirmed (a person would do this: logged)",)),
            ("Shortlist the top 6 (with a reason)", RC_BEHALF, shortlist, ("Screening and the evidence checker",)),
            ("The scoring scale", "code + " + RC_BEHALF, scoring_scale, ("Shortlist the top 6 (with a reason)",)),
            ("Invite 2 to the AI interview and approve the invitations", RC_BEHALF, invite_two, ("Shortlist the top 6 (with a reason)",)),
            ("AI interviews: a strong and a weak simulated candidate", "AI interviewer + simulated candidates", ai_interviews, ("Invite 2 to the AI interview and approve the invitations",)),
            ("Recordings and the recruiter's own review of the AI interviews", "code + " + RC_BEHALF, recordings, ("AI interviews: a strong and a weak simulated candidate",)),
            ("A practice recruiter interview followed by the copilot", "copilot + " + RC_BEHALF, practice_and_copilot, ("Recordings and the recruiter's own review of the AI interviews",)),
            ("The recruiter's scores and decisions", RC_BEHALF, scores_and_decision, ("A practice recruiter interview followed by the copilot",)),
            ("Emails approved", RC_BEHALF, emails, ("The recruiter's scores and decisions",)),
            ("The scorecard", "code", scorecard, ("The recruiter's scores and decisions",)),
        ]
        for name, who, fn, needs in steps:
            j.run(name, who, fn, needs)

    total = round(time.perf_counter() - j.started, 1)
    cost, speed = costing.cost_numbers(), costing.speed_numbers()
    ok = all(r["status"] == "OK" for r in j.rows)
    with SessionLocal() as db:
        without_person = db.scalar(select(func.count()).select_from(DecisionLog).where(DecisionLog.actor == "system", DecisionLog.action.like("final decision%")))
    port = 8003
    links = {"The strong candidate's scorecard": f"/candidates/{S.get('strong', 1)}/scorecard", "The replay room": f"/interviews/{S.get('strong', 1)}/replay",
             "Trust and cost": "/trust", "The pipeline": "/pipeline", "The outbox": "/outbox"}
    serve = (f'DATABASE_URL=sqlite:///data/journey.db OPS_DATABASE_URL=sqlite:///data/journey_ops.db STORAGE_DIR=data/journey_storage FAKE_MODELS={0 if REAL else 1} '
             f"python -m uvicorn app.main:app --port {port}")
    print(f"\n{'ALL STEPS OK' if ok else 'SOME STEPS DID NOT FINISH'}: {sum(r['status'] == 'OK' for r in j.rows)} of {len(j.rows)} in {total} s; total cost ${cost['total_cost']:.4f}"
          f"{' (what the same calls would cost at list prices: fake mode)' if cost['simulated'] else ''}")
    print("To open it in the app, serve the journey's own database:\n  " + serve + "\nand sign in as recruiter@example.com (password demo-password-1), then open:")
    for label, path in links.items():
        print(f"  {label}: http://127.0.0.1:{port}{path}")
    md = ["## Steps", table(["#", "step", "who", "result", "seconds", "detail"], [[r["n"], r["name"], r["who"], r["status"], r["seconds"], r["result"]] for r in j.rows]), "",
          f"Total time: **{total} s**. Total cost: **${cost['total_cost']:.4f}**" + (" (fake mode: what the same calls would cost at list prices)." if cost["simulated"] else " (from the provider's prices)."), "",
          "## Who did what", "Every row marked ON A PERSON'S BEHALF is a step a person does in real use (the hiring manager approves the job; the recruiter confirms unsure fields, shortlists, "
          "invites, enters their own levels, decides and approves every email). The script plays those roles through the same web pages so the whole journey can run; the decision log "
          "records each of them under the person's own account, and the review step carries a note saying a person would do it.", "",
          "## Open it in the app", f"Serve the journey's own database:\n\n    {serve}\n", *[f"- {label}: http://127.0.0.1:{port}{path}" for label, path in links.items()], "",
          "## Limits", "- Fake mode: the AI parts are rule-based stand-ins, so this proves the platform works end to end, not how good a real model is. Run with `--real` for that.",
          "- The AI interviews use recorded answers from the starter kit ('strong' and 'weak' simulated candidates).", ""]
    write_report("journey", "The whole journey in one command", {"mode": mode, "database": "data/journey.db (fresh)", "cvs": 52}, {"steps": j.rows, "total_seconds": total, "cost": cost, "speed": speed,
                                                                                                                            "system_final_decisions": without_person, "links": links}, ok and without_person == 0,
                 "\n".join(md))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
