"""Day 7: what the Ask the data and Data agent screens show (done, not a ticket)."""

import json

from app import store
from app.config import PROBES_FILE_7, ROW_CHECKS_FILE_7
from app.data_agent import access, agent, evaluate, semantic, warehouse
from app.data_agent.row_security import apply_row_security
from app.data_agent.validator import check_query
from app.llm import llm_client, settings
from app.pipeline.service import CLASS_MODEL, GBP_PER_USD, PILOT_MODEL, usd

DEFAULT_LAYER = "caseflow_v1"
QUESTIONS_PER_MONTH = 2000  # an assumption to check with Deborah: about 35 people asking a few questions a working day


def _not_built() -> dict:
    out = {"validator": "", "row_security": ""}
    try:
        check_query("SELECT 1", ["caseflow.cases"])
    except NotImplementedError as e:
        out["validator"] = str(e) or "ENG-701 is not built yet"
    try:
        apply_row_security("SELECT 1 FROM caseflow.cases", ["N1"], {"caseflow.cases": "team_id IN ({teams})"}, [])
    except NotImplementedError as e:
        out["row_security"] = str(e) or "ENG-702 is not built yet"
    return out


def current_layer() -> str:
    name = store.load("data_agent/settings.json", {}).get("layer", DEFAULT_LAYER)
    return name if name in semantic.layers() else DEFAULT_LAYER


def set_layer(name: str) -> dict:
    if name not in semantic.layers():
        raise KeyError(f"No semantic layer {name}")
    store.save("data_agent/settings.json", {"layer": name})
    return {"layer": name}


def status() -> dict:
    s = settings()
    return {"fake": s["fake"], "model": CLASS_MODEL if s["fake"] else s["openrouter_model"], "layers": semantic.layers(),
            "layer": current_layer(), "users": access.users(), "sets": evaluate.sets(), "not_built": _not_built(),
            "as_of": semantic.load(DEFAULT_LAYER).get("as_of")}


def layer(name: str) -> dict:
    L = semantic.load(name)
    return {"name": name, "text": semantic.text(name), "terms": [{"name": k, **v} for k, v in L["terms"].items()],
            "examples": L["examples"], "metrics": [{"name": k, **v} for k, v in (L.get("metrics") or {}).items()],
            "keys": sorted(semantic.keys(L)), "prompt_chars": len(semantic.render(L))}


def warehouse_view(name: str) -> dict:
    L = semantic.load(name)
    pol = access.policy()
    approved = {a.lower() for a in pol["approved_tables"]}
    out = []
    for t in warehouse.tables():
        spec = L.get("tables", {}).get(t["table"], {})
        out.append({**t, "approved": t["table"].lower() in approved, "description": spec.get("description", ""),
                    "columns": [{**c, "description": spec.get("columns", {}).get(c["name"], "")} for c in t["columns"]]})
    return {"layer": name, "tables": out, "joins": L.get("joins", []), "max_rows": pol["max_rows"],
            "row_filters": pol["row_filters"], "roles": pol["roles"], "users": access.users()}


def suggestions(user_id: str) -> list[dict]:
    idx = agent.scripted_index()
    out = []
    for set_name in ("bank30",):
        for q in evaluate.questions(set_name):
            if q["user"] == user_id:
                out.append({"id": q["id"], "question": q["question"]})
    for qid, q in idx.items():
        if qid.startswith("X") and user_id in q.get("users", []):
            out.append({"id": qid, "question": q["question"]})
    return out


def ask(question: str, user_id: str, layer_name: str | None = None) -> dict:
    return agent.ask(question, user_id, layer_name or current_layer(), llm_client()).model_dump()


# ---------------------------------------------------------------- Safety: the probes (ENG-701 and the cost check)
def probes() -> dict:
    nb = _not_built()["validator"]
    pol = access.policy()
    data = json.loads(PROBES_FILE_7.read_text(encoding="utf-8"))["probes"]
    if nb:
        return {"not_built": nb, "probes": [{**p, "verdict": None, "passed": None} for p in data], "summary": None}
    out = []
    for p in data:
        c = check_query(p["sql"], pol["approved_tables"], pol["max_rows"], pol["blocked_functions"])
        row = {**p, "reasons": c.reasons, "notes": c.notes, "sql_run": c.sql, "stage": "validator", "rows": None}
        if c.ok:
            try:
                res = warehouse.run(c.sql)
                row.update(verdict="allow", stage="ran", rows=len(res["rows"]))
            except warehouse.QueryRefused as e:
                row.update(verdict="refuse", stage="cost", reasons=[str(e)])
            except warehouse.QueryFailed as e:
                row.update(verdict="refuse", stage="warehouse", reasons=[str(e)])
        else:
            row["verdict"] = "refuse"
        row["passed"] = row["verdict"] == p["expect"]
        out.append(row)
    refuse = [r for r in out if r["expect"] == "refuse"]
    allow = [r for r in out if r["expect"] == "allow"]
    return {"not_built": "", "probes": out, "summary": {
        "refused": sum(r["passed"] for r in refuse), "should_refuse": len(refuse),
        "allowed": sum(r["passed"] for r in allow), "should_allow": len(allow),
        "by_cost_check": sum(r["stage"] == "cost" for r in out), "passed": sum(r["passed"] for r in out), "total": len(out)}}


# ---------------------------------------------------------------- Row security: the same query as three people (ENG-702)
def row_checks() -> dict:
    nb = _not_built()
    pol = access.policy()
    data = json.loads(ROW_CHECKS_FILE_7.read_text(encoding="utf-8"))["checks"]
    users = [u["id"] for u in pol["users"]]
    if nb["validator"] or nb["row_security"]:
        return {"not_built": nb["row_security"] or nb["validator"], "users": access.users(),
                "checks": [{**c, "results": {}} for c in data], "summary": None}
    out = []
    for c in data:
        results = {}
        for uid in users:
            u = access.user(uid)
            chk = check_query(c["sql"], pol["approved_tables"], pol["max_rows"], pol["blocked_functions"])
            sql = apply_row_security(chk.sql, access.teams_for(u), pol["row_filters"], access.masked_for(u))
            try:
                rows = warehouse.run(sql)["rows"]
                err = ""
            except (warehouse.QueryFailed, warehouse.QueryRefused) as e:
                rows, err = None, str(e)
            exp = c["expected"].get(uid)
            results[uid] = {"rows": rows, "expected": exp, "passed": rows == exp, "secured_sql": sql, "error": err}
        out.append({**c, "results": results})
    cells = [r for c in out for r in c["results"].values()]
    return {"not_built": "", "users": access.users(), "checks": out,
            "summary": {"passed": sum(r["passed"] for r in cells), "total": len(cells),
                        "leaks": sum(1 for r in cells if not r["passed"])}}


# ---------------------------------------------------------------- Evaluation
def _cost(sc: dict) -> dict:
    out = {}
    for key, model in (("class", sc.get("model") or CLASS_MODEL), ("pilot", PILOT_MODEL)):
        u = usd(sc["tokens_in"], sc["tokens_out"], model if model else CLASS_MODEL)
        out[key] = None if u is None else {"model": model, "usd_per_question": round(u, 5),
                                           "gbp_per_month": round(u * QUESTIONS_PER_MONTH * GBP_PER_USD, 2)}
    return out


def eval_view(set_name: str) -> dict:
    runs = []
    for name in semantic.layers():
        r = evaluate.load_run(set_name, name)
        if r:
            sc = evaluate.score(r)
            sc["model"] = r.get("model")
            runs.append({**sc, "cost": _cost(sc)})
    return {"set": set_name, "sets": evaluate.sets(), "layers": semantic.layers(), "runs": runs,
            "questions": [{k: q[k] for k in ("id", "user", "question", "tags")} for q in evaluate.questions(set_name)],
            "questions_per_month": QUESTIONS_PER_MONTH, "not_built": _not_built()}


def eval_run(set_name: str, layer_name: str) -> dict:
    nb = _not_built()
    if nb["validator"] or nb["row_security"]:
        raise NotImplementedError(nb["validator"] or nb["row_security"])
    client = llm_client()
    r = evaluate.run(set_name, layer_name, client)
    if not getattr(client, "is_fake", False):
        r["model"] = settings()["openrouter_model"]
        store.save(f"data_agent/runs/{set_name}__{layer_name}.json", r)
    sc = evaluate.score(r)
    sc["model"] = r.get("model")
    return {**sc, "cost": _cost(sc)}


def eval_results(set_name: str, layer_name: str) -> dict | None:
    return evaluate.load_run(set_name, layer_name)
