"""Load test for /ask: 60 questions drawn from data/operator_questions.csv by weight, 4 users at once, a fixed seed.

    python -m scripts.loadtest --label baseline --routing off --cache off      # Phase 4: the tower as it was built in Part 1
    python -m scripts.loadtest --label after    --routing on  --cache on       # Phase 5: routing, cache and streaming
    python -m scripts.loadtest --report                                        # write PERF_REPORT.md from the saved runs
    python -m scripts.loadtest --label baseline --model real ...               # the same test against the real models

It starts its own API process (so the measurement is the real HTTP path), triages the starter alerts once, resets the
counters, then fires the questions. Two runs with the same seed ask the same questions in the same order.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from tower.metrics import percentile
from tower.settings import ROOT

REPORTS = ROOT / "reports"


def draw_questions(n: int = 60, seed: int = 17) -> list[str]:
    with open(ROOT / "data" / "operator_questions.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rng = random.Random(seed)
    return rng.choices([r["question"] for r in rows], weights=[int(r["weight"]) for r in rows], k=n)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    def __init__(self, env: dict[str, str]):
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        full = {**os.environ, **env, "ALLOW_ADMIN_DEBUG": "1", "PYTHONPATH": str(ROOT), "TOWER_APP_LOG": str(ROOT / "logs" / "loadtest.log"),
                "TOWER_DB": str(ROOT / "data" / "loadtest.db"), "TOWER_ACTIONS_LOG": str(ROOT / "logs" / "loadtest_actions.log")}
        db = Path(full["TOWER_DB"])
        for suffix in ("", "-wal", "-shm"):
            Path(str(db) + suffix).unlink(missing_ok=True)
        self.p = subprocess.Popen([sys.executable, "-m", "uvicorn", "tower.api:create_app", "--factory", "--port", str(self.port),
                                   "--log-level", "warning"], cwd=ROOT, env=full, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def wait(self, timeout: float = 90) -> None:
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if requests.get(self.url + "/ready", timeout=2).status_code == 200:
                    return
            except requests.RequestException:
                pass
            time.sleep(0.5)
        raise RuntimeError("the API did not become ready")

    def stop(self) -> None:
        self.p.terminate()
        try:
            self.p.wait(10)
        except subprocess.TimeoutExpired:
            self.p.kill()
        db = ROOT / "data" / "loadtest.db"
        for suffix in ("", "-wal", "-shm"):
            Path(str(db) + suffix).unlink(missing_ok=True)


def ask_once(url: str, q: str) -> dict:
    t0 = time.perf_counter()
    try:
        r = requests.post(url + "/ask", json={"question": q}, timeout=120)
        ok = r.status_code == 200
        body = r.json() if ok else {}
    except requests.RequestException:
        ok, body = False, {}
    return {"q": q, "ms": (time.perf_counter() - t0) * 1000, "ok": ok, "route": body.get("route"), "answer": body.get("answer", "")}


def stream_once(url: str, q: str) -> dict:
    t0 = time.perf_counter()
    first, total, route = None, None, None
    with requests.post(url + "/ask/stream", json={"question": q}, stream=True, timeout=120) as r:
        for line in r.iter_lines():
            if not line:
                continue
            ev = json.loads(line)
            if ev["type"] == "meta":
                route = ev.get("route")
            if ev["type"] == "chunk" and first is None:
                first = (time.perf_counter() - t0) * 1000
            if ev["type"] == "done":
                total = (time.perf_counter() - t0) * 1000
                ttft = ev.get("ttft_ms")
    return {"route": route, "first_visible_ms": first, "total_ms": total, "ttft_ms": ttft}


def run(label: str, routing: bool, cache: bool, model: str, n: int, users: int, seed: int) -> dict:
    env = {"ROUTING": "1" if routing else "0", "CACHE": "1" if cache else "0", "MODEL_MODE": "openrouter" if model == "real" else "fake",
           "FAKE_LATENCY_SCALE": "1.0"}
    srv = Server(env)
    try:
        srv.wait()
        t0 = time.time()
        tri = requests.post(srv.url + "/triage", json={}, timeout=600).json()
        triage_s = time.time() - t0
        brief_metrics = requests.get(srv.url + "/metrics").json()
        requests.post(srv.url + "/admin/metrics/reset")
        questions = draw_questions(n, seed)
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=users) as ex:
            results = list(ex.map(lambda q: ask_once(srv.url, q), questions))
        wall = time.perf_counter() - t0
        m = requests.get(srv.url + "/metrics").json()
        # streaming: time to first visible text for the questions that go to a model (the cache is cleared so it is a real call)
        requests.post(srv.url + "/admin/cache/clear")
        model_qs = [r["q"] for r in results if r["route"] in ("small", "large", "cache")][:12] or questions[:12]
        streams = [stream_once(srv.url, q) for q in dict.fromkeys(model_qs)][:10]
        lat = [r["ms"] for r in results if r["ok"]]
        out = {
            "label": label, "model": model, "routing": routing, "cache": cache, "seed": seed, "questions": n, "users": users,
            "first_five": questions[:5], "errors": sum(1 for r in results if not r["ok"]),
            "p50_ms": round(percentile(lat, 50), 1), "p95_ms": round(percentile(lat, 95), 1), "throughput_qps": round(n / wall, 2),
            "wall_s": round(wall, 1), "cost_per_1000_usd": m["cost_per_1000_questions_usd"], "cache_hit_rate": m["cache"]["hit_rate"],
            "routes": m["routes"], "route_p50_ms": m["route_p50_ms"], "tokens_total": m["tokens_total"],
            "cost_per_brief_usd": brief_metrics["cost_per_incident_brief_usd"], "briefs": brief_metrics["briefs"], "triage_s": round(triage_s, 1),
            "ttft_ms_p50": round(percentile([s["ttft_ms"] for s in streams if s.get("ttft_ms")], 50), 1),
            "first_visible_ms_p50": round(percentile([s["first_visible_ms"] for s in streams if s["first_visible_ms"]], 50), 1),
            "stream_total_ms_p50": round(percentile([s["total_ms"] for s in streams if s["total_ms"]], 50), 1),
            "stream_n": len(streams), "answers": {r["q"]: r["answer"][:200] for r in results[:12]},
            "models": {"large": m["settings"]["llm_model"], "small": m["settings"]["small_model"]},
        }
        return out
    finally:
        srv.stop()


def write_report() -> None:
    runs = {}
    for p in sorted(REPORTS.glob("perf_*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        runs[(d["model"], d["label"])] = d
    lines = ["# PERF_REPORT: cost and speed, before and after Part 2", "",
             "Load test: **60 questions** drawn from `data/operator_questions.csv` by weight, **4 users at once**, seed **17** "
             "(two runs with the same seed ask the same questions in the same order). Measured over HTTP against the running API.", ""]
    for model, title in (("fake", "Fake model with a latency profile (reproducible, free)"), ("real", "Real models through OpenRouter")):
        b, a = runs.get((model, "baseline")), runs.get((model, "after"))
        if not b and not a:
            continue
        lines += [f"## {title}", ""]
        if (b or a) and model == "fake":
            lines += ["The fake model sleeps a fixed time per call (0.45 s + tokens for the large model, 0.12 s + tokens for the small one) and "
                      "reports token counts estimated from text length. Prices are those configured for the real models, so the cost column is an "
                      "estimate; the speed column shows what the routing and the cache change, not what a provider's latency would be.", ""]
        else:
            r = b or a
            lines += [f"Large model `{r['models']['large']}`, small model `{r['models']['small']}`.", ""]
        lines += ["| Run | p50 | p95 | Throughput | Cost per 1,000 questions | Cache hit rate | Errors |", "|---|---|---|---|---|---|---|"]
        for name, r in (("baseline (routing off, cache off)", b), ("after (routing on, cache on)", a)):
            if r:
                lines.append(f"| {name} | {r['p50_ms'] / 1000:.2f} s | {r['p95_ms'] / 1000:.2f} s | {r['throughput_qps']} q/s | "
                             f"${r['cost_per_1000_usd']:.2f} | {r['cache_hit_rate'] * 100:.0f}% | {r['errors']} |")
        if a and b:
            def pct(x, y):
                return f"{(y - x) / x * 100:+.0f}%" if x else "n/a"
            lines += ["", f"**Change:** p50 {pct(b['p50_ms'], a['p50_ms'])}, p95 {pct(b['p95_ms'], a['p95_ms'])}, "
                      f"cost per 1,000 {pct(b['cost_per_1000_usd'], a['cost_per_1000_usd'])}, throughput {pct(b['throughput_qps'], a['throughput_qps'])}."]
        for name, r in (("baseline", b), ("after", a)):
            if r:
                routes = ", ".join(f"{k} {v}" for k, v in sorted(r["routes"].items()))
                p50s = ", ".join(f"{k} {v / 1000:.2f} s" for k, v in sorted(r["route_p50_ms"].items()))
                lines += ["", f"- **{name}** · where the questions went: {routes} · p50 by route: {p50s} · same first five questions: "
                          f"{'yes' if (b and a and b['first_five'] == a['first_five']) else 'n/a'}"]
        if a:
            lines += ["", f"**Streaming (after):** the model's first token arrives at p50 {a['ttft_ms_p50'] / 1000:.2f} s; the first text a person can read "
                      f"(after the sentence-level output check) at p50 {a['first_visible_ms_p50'] / 1000:.2f} s, against {a['stream_total_ms_p50'] / 1000:.2f} s "
                      f"for the whole answer ({a['stream_n']} model-routed questions)."]
        if b:
            lines += [f"", f"**Cost per incident brief:** ${b['cost_per_brief_usd']:.4f} (investigator + planner + scribe calls, averaged over {b['briefs']} briefs; "
                      f"triage of all 22 alerts took {b['triage_s']} s)."]
        lines.append("")
    qa = REPORTS / "answer_check.json"
    if qa.exists():
        d = json.loads(qa.read_text(encoding="utf-8"))
        lines += ["## Did the answers get worse? Ten answers before and after", "",
                  f"Each question has facts the answer must contain. Model: **{d['model']}**. Before = routing off, cache off; after = routing on, cache on.", "",
                  "| # | Question | Before | After | Route after |", "|---|---|---|---|---|"]
        for i, r in enumerate(d["rows"], 1):
            lines.append(f"| {i} | {r['q']} | {r['before']}/{r['total']} | {r['after']}/{r['total']} | {r['route']} |")
        lines += ["", f"**Total:** before {d['before']}/{d['total']} facts, after {d['after']}/{d['total']} facts. "
                  f"{'No answer got worse.' if d['worse'] == 0 else str(d['worse']) + ' answer(s) got worse: see the rows above.'}", "",
                  "**What this check caught.** The first time it ran with the real models it found one answer that got worse: *Which steps in RB-07 "
                  "need approval?* scored 2/2 on the large model and 0/2 on the small one (`llama-3.1-8b-instruct` said \"steps 2 and 3\"; it is 3 and 4). "
                  "The question is a filter over parsed runbook steps, so a model can only add mistakes. It now goes to the **data route** "
                  "(exact, no model, free), and the check passes. That is the answer to \"which questions are safe without a model\": "
                  "those whose answer is a row, a count or a filter in our own tables. "
                  "A second run caught the small model itself: asked *How do I fail over the core database?* three times with identical context, "
                  "`llama-3.1-8b-instruct` answered correctly twice and once said \"You cannot fail over the core database\". "
                  "The small model is now `google/gemini-2.5-flash-lite`, which gave the same correct answer four times out of four.", ""]
    lines += ["## How to reproduce", "", "```", "python -m scripts.loadtest --label baseline --routing off --cache off",
              "python -m scripts.loadtest --label after --routing on --cache on", "python -m scripts.answer_check", "python -m scripts.loadtest --report", "```", ""]
    (ROOT / "PERF_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print("wrote PERF_REPORT.md")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="baseline")
    ap.add_argument("--routing", choices=["on", "off"], default="off")
    ap.add_argument("--cache", choices=["on", "off"], default="off")
    ap.add_argument("--model", choices=["fake", "real"], default="fake")
    ap.add_argument("--questions", type=int, default=60)
    ap.add_argument("--users", type=int, default=4)
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--show-order", action="store_true", help="print the questions in order and exit (the seed check)")
    a = ap.parse_args()
    if a.show_order:
        print("\n".join(draw_questions(a.questions, a.seed)))
        return
    if a.report:
        write_report()
        return
    res = run(a.label, a.routing == "on", a.cache == "on", a.model, a.questions, a.users, a.seed)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / f"perf_{a.model}_{a.label}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("answers",)}, indent=1))


if __name__ == "__main__":
    main()
