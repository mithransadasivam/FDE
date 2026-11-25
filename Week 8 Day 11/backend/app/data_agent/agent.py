"""The data agent: write one query, check it, run it; repair once (done, not a ticket).

    question ──► model writes one SQL query from the semantic layer
             ──► check_query()          ENG-701: read-only, approved tables, no file access, a row limit
             ──► apply_row_security()   ENG-702: only the rows this user may see
             ──► warehouse.run()        read-only connection, cost check, time limit
    refused or failed? the model gets the reasons and one more try. Still refused or failed: say so, never guess.

The scripted model (FDE_FAKE_LLM=1) knows the questions in data/Day07_* and replies from
tests/fixtures/data_agent/<id>[+<term>…].json: the reply for the terms and examples your semantic layer defines.
"""

import json
import time

from app.config import ACCESS_FILE  # noqa: F401  (documents where the rules live)
from app.data_agent import access, semantic, warehouse
from app.data_agent.models import Answer, Attempt, SQLReply
from app.data_agent.row_security import apply_row_security
from app.data_agent.validator import check_query
from app.llm import FIXTURES, ask_json

PROMPT = "sql_v1"
SCRIPTED = FIXTURES / "data_agent"


class UnknownQuestion(ValueError):
    """The scripted model only knows the questions in the course's question files."""


def prompt_text() -> str:
    from pathlib import Path

    return (Path(__file__).parent / "prompts" / f"{PROMPT}.md").read_text(encoding="utf-8")


def scripted_index() -> dict:
    p = SCRIPTED / "index.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def question_id(question: str) -> str:
    """The id of a question the scripted model knows, matched on its words."""
    norm = " ".join(question.lower().split()).rstrip("?")
    for qid, q in scripted_index().items():
        if " ".join(q["question"].lower().split()).rstrip("?") == norm:
            return qid
    raise UnknownQuestion("The scripted model only knows the questions in the list. "
                          "To ask anything, set OPENROUTER_API_KEY and FDE_MODEL in .env and turn off FDE_FAKE_LLM.")


def scripted_task(qid: str, layer: dict, repair: bool = False) -> str:
    """The fixture for this question and layer: the one whose terms and examples are all in the layer, with the most of them."""
    have = semantic.keys(layer)
    best, best_n = None, -1
    for f in SCRIPTED.glob(f"{qid}*.json"):
        name = f.stem
        if name.endswith(".repair") != repair:
            continue
        base = name.removesuffix(".repair")
        parts = base.split("+")
        if parts[0] != qid:
            continue
        need = set(parts[1:])
        if need <= have and len(need) > best_n:
            best, best_n = name, len(need)
    if best is None:
        raise UnknownQuestion(f"No scripted reply for {qid}{' (repair)' if repair else ''}")
    return f"data_agent/{best}"


def _user_message(question: str, u: dict) -> str:
    return f"Asked by: {u['name']}, {u['title']}\nQuestion: {question}"


def _try(sql: str, u: dict, pol: dict) -> tuple[Attempt, dict | None]:
    check = check_query(sql, pol["approved_tables"], pol.get("max_rows", 1000), pol.get("blocked_functions", []))
    att = Attempt(sql=sql, check=check)
    if not check.ok:
        return att, None
    att.secured_sql = apply_row_security(check.sql, access.teams_for(u), pol.get("row_filters", {}), access.masked_for(u))
    try:
        return att, warehouse.run(att.secured_sql)
    except (warehouse.QueryRefused, warehouse.QueryFailed) as e:
        att.error = str(e)
        return att, None


def ask(question: str, user_id: str, layer_name: str, client, qid: str = "") -> Answer:
    """Answer one question as one user, with one semantic layer."""
    u = access.user(user_id)
    pol = access.policy()
    layer = semantic.load(layer_name)
    fake = getattr(client, "is_fake", False)
    if fake and not qid:
        qid = question_id(question)
    system = prompt_text().replace("{semantic_layer}", semantic.render(layer))
    message = _user_message(question, u)
    started = time.perf_counter()
    n_calls = len(getattr(client, "calls", []))

    reply = ask_json(client, system, message, SQLReply, scripted_task(qid, layer) if fake else "data_agent")
    attempts: list[Attempt] = []
    result = None
    if reply.sql.strip():
        att, result = _try(reply.sql, u, pol)
        attempts.append(att)
        if result is None:  # one repair: the model sees exactly why
            why = ("It was refused: " + "; ".join(att.check.reasons)) if not att.check.ok else f"It failed: {att.error}"
            repair_msg = f"{message}\n\nYour query was:\n```sql\n{reply.sql}\n```\n{why}\nWrite one corrected query."
            try:
                task = scripted_task(qid, layer, repair=True) if fake else "data_agent_repair"
                reply = ask_json(client, system, repair_msg, SQLReply, task)
            except UnknownQuestion:
                pass  # the scripted model has no better idea: it stays refused
            else:
                if reply.sql.strip():
                    att, result = _try(reply.sql, u, pol)
                    attempts.append(att)

    calls = getattr(client, "calls", [])[n_calls:]
    ans = Answer(question=question, question_id=qid, user=user_id, layer=layer_name, status="answered",
                 attempts=attempts, explanation=reply.explanation, assumptions=reply.assumptions,
                 scope=access.describe(u), ms=round((time.perf_counter() - started) * 1000),
                 tokens_in=sum(c.get("input_tokens", 0) for c in calls), tokens_out=sum(c.get("output_tokens", 0) for c in calls))
    if result is not None:
        ans.columns, ans.rows = result["columns"], result["rows"]
        ans.capped = len(result["rows"]) >= pol.get("max_rows", 1000)
    elif not attempts:
        ans.status = "cannot_answer"
        ans.cannot_answer = reply.cannot_answer or "The model wrote no query."
    elif not reply.sql.strip() and reply.cannot_answer:
        ans.status = "cannot_answer"
        ans.cannot_answer = reply.cannot_answer
    else:
        last = attempts[-1]
        ans.status = "error" if last.check.ok and last.error and not last.error.startswith("Too costly") else "refused"
    return ans
