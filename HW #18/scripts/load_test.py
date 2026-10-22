"""Day 16: a load test. Many users ask questions at the same time, the way real traffic arrives:
popular questions often, rare ones seldom, the same question spelled differently.

python -m scripts.load_test --label baseline                     (60 requests, 4 users at once)
python -m scripts.load_test --label cache --requests 60 --users 4
python -m scripts.load_test --label after --clear-cache          (empty the cache first)

Prints latency (p50, p95), throughput, cost per 1,000 questions, cache hits and routes, and saves
the report in logs/load_<label>.json so before and after can be compared (scripts/compare_reports.py).
The questions are drawn by weight with a fixed seed, so every run asks the same questions in the
same order.
"""

import argparse
import csv
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from app.monitoring import percentile

QUESTIONS = "data/Day16_Slide09_load_questions.csv"


def draw(path: str, n: int, seed: int = 16) -> list[str]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rng = random.Random(seed)
    return rng.choices(
        [r["question"] for r in rows], weights=[float(r["weight"]) for r in rows], k=n
    )


def ask(client: httpx.Client, question: str) -> dict:
    start = time.perf_counter()
    try:
        r = client.post("/ask", json={"question": question})
    except httpx.HTTPError as error:
        return {
            "question": question,
            "status": "error",
            "error": type(error).__name__,
            "seconds": round(time.perf_counter() - start, 3),
        }
    seconds = round(
        time.perf_counter() - start, 3
    )  # what the user waited, queueing included
    if r.status_code != 200:
        return {
            "question": question,
            "status": "error",
            "error": str(r.status_code),
            "seconds": seconds,
        }
    body = r.json()
    return {
        "question": question,
        "status": "ok",
        "seconds": seconds,
        "model": body["model"],
        "route": "cache" if body.get("cached") else (body.get("route") or "declined"),
        "cached": body.get("cached", False),
        "cost_usd": body.get("cost_usd", 0.0),
        "tokens": (body.get("prompt_tokens") or 0)
        + (body.get("completion_tokens") or 0),
    }


def report(results: list[dict], wall: float, label: str, users: int) -> dict:
    ok = [r for r in results if r["status"] == "ok"]
    seconds = [r["seconds"] for r in ok]
    cost = sum(r["cost_usd"] for r in ok)
    routes = {}
    for r in ok:
        routes[r["route"]] = routes.get(r["route"], 0) + 1
    return {
        "label": label,
        "requests": len(results),
        "users": users,
        "errors": len(results) - len(ok),
        "p50_seconds": percentile(seconds, 50),
        "p95_seconds": percentile(seconds, 95),
        "throughput_per_second": round(len(results) / wall, 2) if wall else None,
        "wall_seconds": round(wall, 1),
        "cost_usd": round(cost, 6),
        "cost_per_1000": round(cost / len(ok) * 1000, 4) if ok else None,
        "tokens_per_question": round(sum(r["tokens"] for r in ok) / len(ok))
        if ok
        else None,
        "cache_hit_rate": round(sum(r["cached"] for r in ok) / len(ok), 3)
        if ok
        else 0.0,
        "routes": routes,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--questions", default=QUESTIONS)
    p.add_argument("--requests", type=int, default=60)
    p.add_argument("--users", type=int, default=4, help="how many ask at the same time")
    p.add_argument("--label", default="baseline")
    p.add_argument("--clear-cache", action="store_true")
    a = p.parse_args()
    questions = draw(a.questions, a.requests)
    with httpx.Client(base_url=a.url, timeout=180) as client:
        if a.clear_cache:
            print("Cache cleared:", client.post("/cache/clear").json())
        print(
            f"Load test '{a.label}': {a.requests} requests, {a.users} users at once, {a.url}"
        )
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=a.users) as pool:
            results = list(pool.map(lambda q: ask(client, q), questions))
        wall = time.perf_counter() - start
    rep = report(results, wall, a.label, a.users)
    for k, v in rep.items():
        print(f"  {k:22} {v}")
    out = Path(f"logs/load_{a.label}.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(
        json.dumps({"report": rep, "results": results}, indent=2), encoding="utf-8"
    )
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
