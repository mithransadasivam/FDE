"""Phase 11: every case through the Part 1 single agent AND through the team, scored the same way, with model calls,
tokens and seconds. Writes the Part 3 section of EVAL_REPORT.md and docs/eval_results.json (the Evaluation tab reads it).

python -m scripts.compare --llm offline
python -m scripts.compare --llm live                    (takes a while: about 3 s per model call)
python -m scripts.compare --llm live --parallel-sample VOB-002,VOB-003,VOB-007,VOB-009   (also times parallel checks)

The author's own conclusion lives in docs/PART3_DECISION.md and is copied into the report under the numbers.
"""
import argparse
import json
import time

from vendor_desk import config, report
from vendor_desk.backends import make_backend
from vendor_desk.casedesk import CaseDesk
from vendor_desk.evaluate import load_cases, run_part1, score_case, summarise, use_fresh_database
from vendor_desk.llm import make_llm
from vendor_desk.team import LocalWriter

KEYS = ("model_calls", "tool_calls", "tokens", "seconds", "cost_usd")


def run_team(llm, backend, rows, parallel: bool = False, progress=print):
    """All cases through the team. Returns (scores, wall_seconds). A reply adds to its case; its own row is the difference."""
    desk = CaseDesk(llm, backend, LocalWriter(), parallel)
    scores, started = [], time.monotonic()
    for row in rows:
        rid = row["request_file"].removesuffix(".txt")
        cid = "VOB-" + row["id"][4:7]
        before = dict((desk.case(cid) or {}).get("usage", {}))
        t0 = time.monotonic()
        case = desk.reply(cid, rid) if "-R" in row["id"] else desk.submit(rid)
        wall = time.monotonic() - t0
        usage = {k: round(case["usage"][k] - before.get(k, 0), 5) for k in KEYS}
        usage["wall_seconds"] = round(wall, 2)
        assessment = None
        if case.get("decision"):
            assessment = {"recommended_decision": case["decision"], "flags": case["flags"],
                          "missing_items": case["missing_items"], "approvers_required": case["approvers_required"],
                          "checks": case["checks"]}
        sc = score_case(row, assessment, case["status"], usage, [])
        scores.append(sc)
        progress(f"team {row['id']:<11} expected {row['expected_decision']:<19} got {str(sc.got):<19} "
                 f"calls {usage['model_calls']:.0f}/{usage['tool_calls']:.0f} {wall:.1f}s")
    desk.close()
    return scores, time.monotonic() - started


def row_stats(scores) -> dict:
    t = summarise(scores)
    n = max(t["cases"], 1)
    return {**t, "model_calls_per_case": round(t["model_calls"] / n, 1), "tokens_per_case": round(t["tokens"] / n),
            "seconds_per_case": round(t["seconds"] / n, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", choices=["live", "offline"], default="offline")
    ap.add_argument("--tools", choices=["local", "mcp"], default="local")
    ap.add_argument("--only", default="")
    ap.add_argument("--parallel-sample", default="", help="comma-separated case ids to time sequential vs parallel")
    ap.add_argument("--no-report", action="store_true")
    args = ap.parse_args()

    use_fresh_database()
    config.RUNS_DIR = config.ROOT / "runs" / f"compare_{args.llm}"      # keep the demo data in runs/team untouched
    import shutil
    shutil.rmtree(config.RUNS_DIR, ignore_errors=True)
    only = {c.strip() for c in args.only.split(",") if c.strip()}
    rows = [r for r in load_cases() if not only or r["id"] in only]
    llm, backend = make_llm(args.llm), make_backend(args.tools)

    print("--- Part 1 single agent ---")
    p1 = run_part1(llm, backend, engine="single", only=only or None)
    print("--- team ---")
    team_scores, team_wall = run_team(llm, backend, rows)
    a, b = row_stats(p1["scores"]), row_stats(team_scores)

    parallel = None
    if args.parallel_sample:
        ids = {c.strip() for c in args.parallel_sample.split(",")}
        sample = [r for r in load_cases() if r["id"] in ids]
        shutil.rmtree(config.RUNS_DIR / "team", ignore_errors=True)
        _, seq = run_team(llm, backend, sample, parallel=False, progress=lambda *_: None)
        shutil.rmtree(config.RUNS_DIR / "team", ignore_errors=True)
        _, par = run_team(llm, backend, sample, parallel=True, progress=lambda *_: None)
        parallel = {"cases": sorted(ids), "sequential_seconds": round(seq, 1), "parallel_seconds": round(par, 1)}

    results = {"mode": args.llm, "tools": args.tools, "single": a, "team": b,
               "team_wall_seconds": round(team_wall, 1), "parallel": parallel,
               "per_case": [{"id": s.id, "expected": s.expected, "single": x.got, "team": s.got,
                             "single_calls": x.usage.get("model_calls", 0), "team_calls": s.usage.get("model_calls", 0),
                             "single_tokens": x.usage.get("tokens", 0), "team_tokens": s.usage.get("tokens", 0)}
                            for x, s in zip(p1["scores"], team_scores)]}
    path = config.ROOT / "docs" / "eval_results.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    existing[args.llm] = results
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    def line(label, key, fmt="{}"):
        return [label, fmt.format(a[key]), fmt.format(b[key])]

    table = report.table(["Measure", "Part 1 single agent", "Team (supervisor + specialists)"], [
        ["Cases", a["cases"], b["cases"]],
        ["Decisions right", f"{a['decisions_right']}/{a['cases']}", f"{b['decisions_right']}/{b['cases']}"],
        ["Unsafe misses (said ready where a person/rejection was expected)", a["unsafe_misses"], b["unsafe_misses"]],
        ["Missing items found", f"{a['missing_items_found']}/{a['cases']}", f"{b['missing_items_found']}/{b['cases']}"],
        ["Expected flags found", f"{a['flags_found']}/{a['cases']}", f"{b['flags_found']}/{b['cases']}"],
        ["Approvers right", f"{a['approvers_right']}/{a['cases']}", f"{b['approvers_right']}/{b['cases']}"],
        ["Injection cases handled", f"{a['injection_handled']}/{a['injection_cases']}", f"{b['injection_handled']}/{b['injection_cases']}"],
        line("Model calls (total)", "model_calls"), line("Model calls per case", "model_calls_per_case"),
        line("Tool calls (total)", "tool_calls"), line("Tokens (total)", "tokens", "{:,}"),
        line("Tokens per case", "tokens_per_case", "{:,}"), line("Model seconds (total)", "seconds"),
        line("Cost in USD (from INPUT_PRICE/OUTPUT_PRICE)", "cost_usd"),
        ["Wall-clock seconds, all cases", "-", round(team_wall, 1)],
    ])
    per = report.table(["Case", "Expected", "Single agent", "Team", "Single calls", "Team calls", "Single tokens", "Team tokens"],
                       [[c["id"], c["expected"], c["single"], c["team"], c["single_calls"], c["team_calls"],
                         f"{c['single_tokens']:,}", f"{c['team_tokens']:,}"] for c in results["per_case"]])
    text = [f"Both run on the same {args.llm} model with {args.tools} tools, assessment date {config.AS_OF_DATE}. "
            "The team includes its follow-up drafts and reviewer; the single agent drafts follow-ups with a template.", "",
            "### Scorecard", "", table, "", "### Per case", "", per, ""]
    if parallel:
        saved = parallel["sequential_seconds"] - parallel["parallel_seconds"]
        text += ["### Parallel checks (stretch)", "",
                 f"`documents` and `finance` run at the same time (compliance waits for the tax ID). On {len(parallel['cases'])} "
                 f"cases ({', '.join(parallel['cases'])}): sequential {parallel['sequential_seconds']} s, parallel "
                 f"{parallel['parallel_seconds']} s, a difference of {saved:+.1f} s. Decisions were identical.", ""]
    decision_file = config.ROOT / "docs" / "PART3_DECISION.md"
    if decision_file.exists() and args.llm == "live":
        text += ["### Is the team worth its cost? My decision", "", decision_file.read_text(encoding="utf-8").strip(), ""]
    if not args.no_report and not only:
        kind = "offline baseline" if args.llm == "offline" else "live model"
        report.write_section(f"Part 3: team vs single agent ({kind})", "\n".join(text))
        print("Wrote the Part 3 section of EVAL_REPORT.md")
    print(json.dumps({"single": a, "team": b}, indent=1))


if __name__ == "__main__":
    main()
