"""Homework: run the operations agent on the bank's 20 evaluation cases, in shadow mode, and score each run (done).

Shadow mode: the agent works each exception as Helen Achebe (the MLRO sees every team), and every approval it asks for
is refused and recorded. So the agent goes as far as CaseFlow's confirm screen, and nothing is written.
Results: engagement/agent/evals/<prompt>.json. From backend/: python -m scripts.run_agent_eval --prompt ops_v1
"""

import json
import time

from app import store
from app.agent import runs
from app.agent.approvals import gate
from app.agent.scoring import score_run
from app.config import EVAL_CASES_FILE_9
from app.integration import auth


def cases() -> dict:
    return json.loads(EVAL_CASES_FILE_9.read_text(encoding="utf-8"))


def gate_is_built() -> bool:
    """Shadow mode depends on the gate asking before Confirm (ENG-903): without it, the runs would write to CaseFlow."""
    d = gate({"system": "caseflow", "tool": "click", "target": "Confirm", "fingerprint": "probe"}, runs.rules(), [], 0)
    return d.kind == "ask"


def evaluate(prompt: str = "ops_v1", only: list[str] | None = None, identity=None, progress=print) -> dict:
    if not gate_is_built():
        raise RuntimeError("Build ENG-903 first: shadow mode relies on the gate asking before Confirm, or the runs would write to CaseFlow")
    spec = cases()
    ident = identity or runs.identity_for(auth.sign_in_as(spec["run_as"]))
    lim = runs.limits()
    results, scored = [], True
    for c in spec["cases"]:
        if only and c["id"] not in only and c["ticket_id"] not in only:
            continue
        run = runs.execute_run(runs.new_run(c["ticket_id"], ident.sub, prompt, mode="shadow"), ident, approver=runs.shadow_approver)
        r = run.model_dump()
        try:
            s = score_run(r, c, lim)
        except NotImplementedError as e:
            s, scored = {"checks": {}, "passed": None, "error": str(e)}, False
        results.append({**c, "run_id": run.id, "status": run.status, "outcome": run.outcome, "reason_code": run.reason_code,
                        "stop_reason": run.stop_reason, "steps": len(run.steps), "tokens_in": run.tokens_in, "tokens_out": run.tokens_out,
                        "cost_usd": run.cost_usd, "score": s})
        progress(f"{c['id']} {c['ticket_id']}: {run.status} {run.outcome or run.stop_reason} -> "
                 f"{'pass' if s.get('passed') else ('not scored' if s.get('passed') is None else 'FAIL')}")
    passed = sum(1 for x in results if x["score"].get("passed"))
    out = {"prompt": prompt, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "run_as": ident.sub, "scored": scored, "passed": passed,
           "total": len(results), "tokens_in": sum(x["tokens_in"] for x in results), "tokens_out": sum(x["tokens_out"] for x in results),
           "cost_usd": round(sum(x["cost_usd"] or 0 for x in results), 6), "results": results}
    if not only:
        store.save(f"agent/evals/{prompt}.json", out)
    return out


def saved() -> list[dict]:
    d = store.path("agent/evals")
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))] if d.exists() else []
