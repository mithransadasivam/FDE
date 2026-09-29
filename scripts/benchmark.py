"""Day 3 homework, Task 2: send every prompt in data/prompts.txt to every backend.

Run: python -m scripts.benchmark
Writes data/benchmark.csv (add your 1-5 quality score in the empty `score` column)
and prints a per-backend summary.
"""

import csv
import time

from app.chatbot import build_backends

PROMPTS = "data/prompts.txt"
OUT = "data/benchmark.csv"
FIELDS = [
    "prompt_no",
    "backend",
    "model",
    "seconds",
    "input_tokens",
    "output_tokens",
    "cost",
    "score",
    "answer",
]


def read_prompts(path=PROMPTS):
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def run_one(backend, prompt, clock=time.perf_counter):
    """One call. Returns a result dict; errors are recorded, not raised."""
    start = clock()
    try:
        r = backend.client.chat.completions.create(
            model=backend.model, messages=[{"role": "user", "content": prompt}]
        )
    except Exception as e:  # noqa: BLE001 - keep going: one failed call must not lose the run
        return {
            "seconds": clock() - start,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
            "answer": f"ERROR: {type(e).__name__}: {e}",
        }
    seconds = clock() - start
    p = getattr(r.usage, "prompt_tokens", 0) or 0
    c = getattr(r.usage, "completion_tokens", 0) or 0
    return {
        "seconds": seconds,
        "input_tokens": p,
        "output_tokens": c,
        "cost": p / 1e6 * backend.in_price + c / 1e6 * backend.out_price,
        "answer": r.choices[0].message.content or "",
    }


def run_benchmark(backends, prompts, clock=time.perf_counter):
    rows = []
    for i, prompt in enumerate(prompts, 1):
        for name, b in backends.items():
            res = run_one(b, prompt, clock)
            rows.append(
                {
                    "prompt_no": i,
                    "backend": name,
                    "model": b.model,
                    "seconds": round(res["seconds"], 2),
                    "input_tokens": res["input_tokens"],
                    "output_tokens": res["output_tokens"],
                    "cost": round(res["cost"], 6),
                    "score": "",
                    "answer": res["answer"],
                }
            )
            print(f"prompt {i:2} {name:8} {res['seconds']:6.1f}s")
    return rows


def write_csv(rows, path=OUT):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def summarise(rows):
    """Per backend: calls, average seconds, total cost."""
    out = {}
    for r in rows:
        s = out.setdefault(r["backend"], {"calls": 0, "seconds": 0.0, "cost": 0.0})
        s["calls"] += 1
        s["seconds"] += float(r["seconds"])
        s["cost"] += float(r["cost"])
    return {
        k: {
            "calls": v["calls"],
            "avg_seconds": v["seconds"] / v["calls"],
            "total_cost": v["cost"],
        }
        for k, v in out.items()
    }


def format_summary(summary):
    lines = [f"{'backend':10} {'calls':>5} {'avg s':>7} {'total $':>9}"]
    for name, s in summary.items():
        lines.append(
            f"{name:10} {s['calls']:5} {s['avg_seconds']:7.2f} {s['total_cost']:9.4f}"
        )
    return "\n".join(lines)


def main():
    backends = build_backends()
    rows = run_benchmark(backends, read_prompts())
    write_csv(rows)
    print("\n" + format_summary(summarise(rows)))
    print(f"\nWrote {OUT}. Now fill in the score column (1-5) for each row.")


if __name__ == "__main__":
    main()
