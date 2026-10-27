"""Performance and cost (Day 4, BR-17): cost per 100 CVs and per AI interview, and how fast the voice interview responds, before and after
routing and caching. Writes evidence/perf.json and PERF_REPORT.md.

Run:  python -m scripts.run_perf        (about a minute: it reads and screens all 52 CVs and runs 5 interviews, in a temporary database)

Read this honestly:
 * Fake mode calls no model, so TOKEN COUNTS are real (estimated as characters / 4) but COSTS are what those tokens would cost at the list
   prices in app/ai/router.py, and model LATENCY is an assumption (constants below). The compute time of the platform itself is measured.
 * Replace the constants with your provider's numbers, or run with real models, for figures you can quote.
"""
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="perf_"))
os.environ.update({"FAKE_MODELS": "1", "DATABASE_URL": f"sqlite:///{(_TMP / 'p.db').as_posix()}", "OPS_DATABASE_URL": f"sqlite:///{(_TMP / 'ops.db').as_posix()}",
                   "STORAGE_DIR": str(_TMP / "storage"), "SECRET_KEY": "perf-secret-not-real", "OPENROUTER_API_KEY": ""})

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.agents import assistant  # noqa: E402
from app.ai import router  # noqa: E402
from app.ai.llm import clear_cache  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import Base, OpsBase, OpsSession, SessionLocal, engine, ops_engine  # noqa: E402
from app.interview.replay import run_recorded_interview  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Candidate, Requisition  # noqa: E402
from app.models_ext import AgentTrace, ModelCall  # noqa: E402
from app.search import index as search_index  # noqa: E402
from scripts.create_users import DEMO_PASSWORD, create_users  # noqa: E402
from scripts.upload_cvs import DEFAULT_FOLDER, upload_all  # noqa: E402

KIT = Path("starter_kit")
# ---- assumptions (editable): what the models and the voice services cost and how long they take -----------------------------------------------
ASSUME = {
    "stt_usd_per_minute": 0.006, "tts_usd_per_1k_chars": 0.015,  # speech-to-text and text-to-speech list prices
    "stt_latency_s": 0.35, "llm_scoring_latency_s": 1.10, "tts_first_audio_s": 0.40, "network_margin_s": 0.30,  # seconds, per turn
    "avg_answer_seconds": 22.0,
}
VOICE_TARGET_S = 2.5


def p95(xs: list[float]) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))] if xs else 0.0


def cost(tokens_in: int, tokens_out: int, tier: str) -> float:
    return router.cost_usd(tier, tokens_in, tokens_out)


def world() -> tuple[TestClient, TestClient]:
    Base.metadata.drop_all(engine)
    OpsBase.metadata.drop_all(ops_engine)
    Base.metadata.create_all(engine)
    OpsBase.metadata.create_all(ops_engine)
    clear_cache()
    with SessionLocal() as db:
        create_users(db)
    hm, visitor = TestClient(app, follow_redirects=False), TestClient(app, follow_redirects=False)
    hm.__enter__()
    visitor.__enter__()
    hm.post("/login", data={"email": "hm@example.com", "password": DEMO_PASSWORD})
    note = KIT / "voice_notes" / "REQ_cloud_support_engineer.wav"
    hm.post("/requisitions", data={"title": "Cloud Support Engineer"}, files={"audio": (note.name, note.read_bytes(), "audio/wav")})
    for step in ("generate", "approve", "publish"):
        hm.post(f"/requisitions/1/{step}", data={"comment": "perf"})
    return hm, visitor


def ledger(agent: str | None = None, since: int = 0) -> list[ModelCall]:
    with OpsSession() as ops:
        q = select(ModelCall).where(ModelCall.id > since)
        if agent:
            q = q.where(ModelCall.agent == agent)
        return list(ops.scalars(q))


def last_id() -> int:
    with OpsSession() as ops:
        return ops.scalars(select(ModelCall.id).order_by(ModelCall.id.desc())).first() or 0


def main() -> int:
    s = get_settings()
    s.cache_enabled = False
    hm, visitor = world()

    # ---- 1. cost per 100 CVs: read 52 CVs, screen them --------------------------------------------------------------------------------------------
    t0 = time.perf_counter()
    upload_all(visitor, 1, DEFAULT_FOLDER)
    read_seconds = time.perf_counter() - t0
    with SessionLocal() as db:
        n_cv = db.query(Candidate).count()
        for c in db.query(Candidate).filter_by(stage="REVIEW"):
            c.stage = "EXTRACTED"  # the perf run scores everyone; a person would normally confirm the scans first
        db.commit()
        from app.agents.screening import screen_requisition
        t1 = time.perf_counter()
        screen_requisition(db, 1, "perf")
        screen_seconds = time.perf_counter() - t1
    calls = [c for c in ledger() if c.agent in ("document", "screening")]
    tin, tout = sum(c.tokens_in for c in calls), sum(c.tokens_out for c in calls)
    ex = [c for c in calls if c.task == "identity"]
    sc = [c for c in calls if c.task == "scoring"]
    # before routing: every call uses the large model (and CV text, with identity, goes to a hosted model); after: extraction on the local model
    before = cost(sum(c.tokens_in for c in calls), sum(c.tokens_out for c in calls), "large")
    after = cost(sum(c.tokens_in for c in ex), sum(c.tokens_out for c in ex), "local") + cost(sum(c.tokens_in for c in sc), sum(c.tokens_out for c in sc), "large")
    after_small_extract = cost(sum(c.tokens_in for c in ex), sum(c.tokens_out for c in ex), "small") + cost(sum(c.tokens_in for c in sc), sum(c.tokens_out for c in sc), "large")
    per100 = lambda x: round(x / n_cv * 100, 4)  # noqa: E731

    # ---- 2. cost and speed of the AI interview: 5 interviews from recorded answers ----------------------------------------------------------------------------
    with SessionLocal() as db:
        from app.models import DecisionLog  # noqa: F401
        from app.shortlist import approve_shortlist, suggest_shortlist
        entries = suggest_shortlist(db, 1)
        ids = [e.candidate_id for e in entries[:5]]
        approve_shortlist(db, 1, ids, "recruiter@example.com", "perf run")
        from app.supervisor import move
        from app.schemas import Stage
        for cid in ids:
            move(db, db.get(Candidate, cid), Stage.AI_INTERVIEW, "recruiter@example.com", "perf run")
        db.commit()
        mark = last_id()
        with OpsSession() as ops:
            trace_mark = ops.scalars(select(AgentTrace.id).order_by(AgentTrace.id.desc())).first() or 0
        wall = []
        for cid in ids:
            t = time.perf_counter()
            run_recorded_interview(db, db.get(Candidate, cid), db.get(Requisition, 1), "strong")
            wall.append(time.perf_counter() - t)
    iv_calls = ledger("interviewer", mark)
    n_iv = len(ids)
    iv_tokens_in, iv_tokens_out = sum(c.tokens_in for c in iv_calls), sum(c.tokens_out for c in iv_calls)
    llm_per_iv = cost(iv_tokens_in, iv_tokens_out, "large") / n_iv
    with OpsSession() as ops:
        spans = list(ops.scalars(select(AgentTrace).where(AgentTrace.agent == "interviewer", AgentTrace.id > trace_mark)))
    # per answer: time from the candidate finishing to the next question starting = listen + score_answer + speak (+ show_diagram)
    per_turn: list[float] = []
    cur = 0.0
    for sp in spans:
        if sp.name in ("listen", "score_answer", "show_diagram", "speak"):
            cur += sp.duration_ms
            if sp.name == "speak":
                per_turn.append(cur)
                cur = 0.0
    questions = 8  # an interview has up to 8 questions
    stt = ASSUME["avg_answer_seconds"] * questions / 60 * ASSUME["stt_usd_per_minute"]
    tts = 8 * 160 / 1000 * ASSUME["tts_usd_per_1k_chars"]
    p95_compute_ms = round(p95(per_turn), 2)
    est = p95_compute_ms / 1000 + ASSUME["stt_latency_s"] + ASSUME["llm_scoring_latency_s"] + ASSUME["tts_first_audio_s"] + ASSUME["network_margin_s"]

    # ---- 3. caching ----------------------------------------------------------------------------------------------------------------------------------------
    qs = ["Who has Kubernetes?", "Which candidates have Terraform?", "How long are recordings kept?", "Who has Linux and Python?", "Who has a certification?"]
    out = {}
    for label, on in (("cache_off", False), ("cache_on", True)):
        s.cache_enabled = on
        assistant._CACHE.clear()
        search_index._CV_INDEX_CACHE.clear()
        clear_cache()
        search_index.INDEX_BUILDS.update(built=0, reused=0)
        m = last_id()
        t = time.perf_counter()
        with SessionLocal() as db:
            for _ in range(3):  # each question is asked three times
                for q in qs:
                    assistant.answer(db, q)
        elapsed = time.perf_counter() - t
        c = ledger("assistant", m)
        out[label] = {"asked": 15, "model_calls_paid": sum(1 for x in c if not x.cached), "cost_usd": round(sum(x.cost_usd for x in c), 5), "seconds": round(elapsed, 3),
                      "index_builds": search_index.INDEX_BUILDS["built"]}
    # a second screening run of the same pool: the model-call cache
    s.cache_enabled = True
    clear_cache()
    with SessionLocal() as db:
        for c in db.query(Candidate).filter_by(stage="SCREENED").limit(5):
            c.stage = "EXTRACTED"
        db.commit()
        m = last_id()
        from app.agents.screening import screen_requisition as sr
        sr(db, 1, "perf")
        first = ledger("screening", m)
        for c in db.query(Candidate).filter(Candidate.id.in_([x.candidate_id for x in first])):
            c.stage = "EXTRACTED"
        db.commit()
        m2 = last_id()
        sr(db, 1, "perf")
        second = ledger("screening", m2)
    out["rescreen"] = {"first_run_paid": sum(1 for x in first if not x.cached), "second_run_paid": sum(1 for x in second if not x.cached), "second_run_cached": sum(1 for x in second if x.cached)}

    report = {
        "assumptions": ASSUME, "n_cvs": n_cv, "n_interviews": n_iv, "fake_mode": True,
        "cost": {"per_100_cvs_before": per100(before), "per_100_cvs_after": per100(after), "per_100_cvs_after_small_extraction": per100(after_small_extract),
                 "tokens_in": tin, "tokens_out": tout, "extraction_tokens": sum(c.tokens_in + c.tokens_out for c in ex), "scoring_tokens": sum(c.tokens_in + c.tokens_out for c in sc),
                 "per_ai_interview_llm": round(llm_per_iv, 5), "per_ai_interview_stt": round(stt, 5), "per_ai_interview_tts": round(tts, 5),
                 "per_ai_interview_total": round(llm_per_iv + stt + tts, 5)},
        "speed": {"read_52_cvs_seconds": round(read_seconds, 1), "screen_52_cvs_seconds": round(screen_seconds, 2), "interview_compute_seconds_each": round(statistics.mean(wall), 3)},
        "voice": {"turns_measured": len(per_turn), "p50_compute_ms": round(statistics.median(per_turn), 2) if per_turn else 0, "p95_compute_ms": p95_compute_ms,
                  "p95_estimated_s": round(est, 2), "target_s": VOICE_TARGET_S, "passed": est <= VOICE_TARGET_S},
        "caching": out,
    }
    Path("evidence").mkdir(exist_ok=True)
    Path("evidence/perf.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    from scripts.reports import write_perf_report
    write_perf_report(report)
    c = report["cost"]
    print(f"Cost per 100 CVs: ${c['per_100_cvs_before']} before routing -> ${c['per_100_cvs_after']} after (extraction on the local model); per AI interview ${c['per_ai_interview_total']}")
    print(f"Voice: p95 compute {p95_compute_ms} ms; estimated p95 {report['voice']['p95_estimated_s']} s (target {VOICE_TARGET_S} s)  {'PASS' if report['voice']['passed'] else 'FAIL'}")
    print(f"Assistant, 15 questions: {out['cache_off']['model_calls_paid']} paid calls without caching, {out['cache_on']['model_calls_paid']} with; rescreen second run paid {out['rescreen']['second_run_paid']} of {len(second)}")
    return 0 if report["voice"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
