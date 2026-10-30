"""The Trust & cost tab: the quality bar (every number comes from an evidence file), what the platform costs, and live checks."""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.compliance import ComplianceAgent
from app.auth import STAFF
from app.db import OpsSession, get_db
from app.models import Candidate, DecisionLog, User
from app.models_ext import AgentTrace, ComplianceFinding, EmailDraft, InterviewSession, ItemScoreRow, ModelCall, OutboxLog
from app.web.common import render

router = APIRouter(prefix="/trust")
EVIDENCE = Path("evidence")


def load(name: str) -> dict | None:
    p = EVIDENCE / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def quality_bar(db: Session) -> list[dict]:
    """The numbers the course checks, each with its target, what was measured, the evidence file and whether it passes."""
    rows = []

    def add(what, target, measured, source, passed):
        rows.append({"what": what, "target": target, "measured": measured, "source": source, "passed": passed})

    ex = load("eval_extraction.json")
    add("CV extraction", ">= 90% of fields right", f"{ex['pct']}%" if ex else "not run", "evidence/eval_extraction.json", bool(ex and ex["pct"] >= 90))
    scan = ComplianceAgent(db).call("scan_prompt_log")
    add("Identity hidden", "0 protected details in any scoring prompt", f"{len(scan)} found", "live scan of the prompt log", not scan)
    scores = list(db.scalars(select(ItemScoreRow).where(ItemScoreRow.score > 0)))
    ok = sum(1 for r in scores if r.verified and r.status == "ok")
    add("Evidence", "100% of scores have a verified quote", f"{ok}/{len(scores)}", "live check of every score", ok == len(scores))
    rk = load("eval_ranking.json")
    add("Shortlist", "top-5 overlap >= 4 of 5", ", ".join(f"{r['role'].split('_')[0]} {r['overlap']}/5" for r in rk["roles"]) if rk else "not run", "evidence/eval_ranking.json", bool(rk and rk["passed"]))
    iv = load("eval_interview.json")
    add("Interview scoring", ">= 80% agreement on 30 answers", f"{iv['scorer_agreement_with_key_pct']}%" if iv else "not run", "evidence/eval_interview.json", bool(iv and iv["passed"]))
    cp = load("eval_copilot.json")
    add("Copilot key points", ">= 80% agreement on 4 recordings", f"{cp['key_point_agreement_pct']}%" if cp else "not run", "evidence/eval_copilot.json", bool(cp and cp["key_point_agreement_pct"] >= 80))
    add("Forbidden question", "flagged within 3 s, every time", (f"{max(f['lag_s'] for f in cp['forbidden_flags'] if 'lag_s' in f):.3f} s" if cp and cp["forbidden_flags"] else "not run"),
        "evidence/eval_copilot.json", bool(cp and cp["passed"]))
    rt = load("red_team.json")
    add("Red team", ">= 18 of 20 attacks stopped", f"{rt['stopped_after']}/20 (was {rt['stopped_before']}/20)" if rt else "not run", "evidence/red_team.json", bool(rt and rt["passed"]))
    log_findings = ComplianceAgent(db).call("check_log")
    add("Approvals", "0 decisions, messages or stage moves without a person", f"{len(log_findings)} found", "live check of the decision log", not log_findings)
    pf = load("perf.json")
    add("Voice speed", "next question within 2.5 s at p95", f"{pf['voice']['p95_estimated_s']} s (compute alone {pf['voice']['p95_compute_ms']} ms)" if pf else "not run", "evidence/perf.json", bool(pf and pf["voice"]["passed"]))
    bs = load("bias_screening.json")
    add("Bias, screening", "no unexplained score difference between variants", f"{bs['unexplained_differences']} differences over {bs['variants']} CVs" if bs else "not run", "evidence/bias_screening.json", bool(bs and bs["passed"]))
    ba = load("bias_accents.json")
    add("Bias, transcription", "differences above 0.5 point reported as findings", f"{len(ba['findings'])} finding(s) reported" if ba else "not run", "evidence/bias_accents.json", bool(ba and ba["reported"]))
    gv = load("governance_check.json")
    add("Governance", "check passes; every claim has evidence with a hash", "PASS" if gv and gv["passed"] else ("FAIL" if gv else "not run"), "evidence/governance_check.json", bool(gv and gv["passed"]))
    return rows


def cost_summary() -> dict:
    with OpsSession() as ops:
        calls = list(ops.scalars(select(ModelCall)))
        steps = ops.execute(select(AgentTrace.agent, func.count(AgentTrace.id), func.avg(AgentTrace.duration_ms)).group_by(AgentTrace.agent)).all()
    by_agent: dict[str, dict] = {}
    for c in calls:
        a = by_agent.setdefault(c.agent or "?", {"calls": 0, "cost": 0.0, "tokens": 0, "cached": 0})
        a["calls"] += 1
        a["cost"] += c.cost_usd
        a["tokens"] += c.tokens_in + c.tokens_out
        a["cached"] += 1 if c.cached else 0
    return {"by_agent": by_agent, "total_cost": round(sum(c.cost_usd for c in calls), 4), "calls": len(calls),
            "simulated": all(c.simulated for c in calls) if calls else True, "steps": [(a, n, round(d or 0, 2)) for a, n, d in steps]}


@router.get("")
def trust(request: Request, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    cs = cost_summary()
    n_cv = db.scalar(select(func.count(Candidate.id))) or 0
    n_iv = db.scalar(select(func.count(InterviewSession.id)).where(InterviewSession.status == "DONE")) or 0
    cv_cost = sum(v["cost"] for k, v in cs["by_agent"].items() if k in ("document", "screening"))
    iv_cost = cs["by_agent"].get("interviewer", {}).get("cost", 0.0)
    counts = {"decisions_logged": db.scalar(select(func.count(DecisionLog.id))), "emails_sent": db.scalar(select(func.count(OutboxLog.id))),
              "drafts_waiting": db.scalar(select(func.count(EmailDraft.id)).where(EmailDraft.status == "DRAFT")),
              "open_findings": db.scalar(select(func.count(ComplianceFinding.id)).where(ComplianceFinding.status == "OPEN"))}
    from app import costing

    costs = costing.cost_numbers()
    return render(request, "trust.html", user, bar=quality_bar(db), cost=cs, counts=counts, perf=load("perf.json"), costs=costs, speed=costing.speed_numbers(),
                  reports=costing.latest_reports(), copilot_times=costing.copilot_warning_times(),
                  cost_per_100_cvs=costs["per_100_cvs"] if costs["per_100_cvs"] is not None else (round(cv_cost / n_cv * 100, 4) if n_cv else None),
                  cost_per_interview=costs["per_interview"]["per_unit"] if costs["per_interview"]["per_unit"] is not None else (round(iv_cost / n_iv, 4) if n_iv else None),
                  n_cv=n_cv, n_iv=n_iv)
