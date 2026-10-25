"""The Tower: one object that holds the settings, database, catalogue, models, guardrails, crew, actions and metrics.
The API, the scripts and the tests all go through it."""
from __future__ import annotations

import queue
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Iterator

from . import ask as askmod
from . import db, guardrails, prompts
from .actions import Actions
from .catalog import Catalog, load as load_catalog
from .crew import Crew
from .llm import LLMError, LLMResult, make_llm
from .metrics import Metrics
from .models import Alert, AlertView, Incident
from .observability import Tracer, get_logger, request_id_var
from .rag import Index
from .settings import Settings
from .tools import ToolGateway, parse_calls
from .triage import TIME_FMT, triage as run_triage, t as parse_time


class Tower:
    def __init__(self, settings: Settings | None = None, llm=None):
        self.s = settings or Settings.from_env()
        db.ensure(self.s.db_path)
        self.log = get_logger()
        con = self.con()
        self.cat: Catalog = load_catalog(con, self.s.root)
        con.close()
        guardrails.register_private_values(db.load_private_for_redaction(self.s.db_path))
        for a in self.starter_alerts():  # the redactor learns any secret value already in the stored alerts
            guardrails.redact(a.message)
        self.llm = llm or make_llm(self.s)
        self.metrics = Metrics(self.s)
        self.tracer = Tracer(self.s.phoenix_endpoint)
        self.index = Index(self.cat)
        self.cache = askmod.AnswerCache(self.s.cache_ttl_s)
        self._offset = timedelta(0)
        self.model_down = False
        self.actions = Actions(self.s, self.cat, self.clock)
        self.gateway = ToolGateway(self.cat, self.audit, self._page,
                                   self._unsafe_execute if not self.s.approvals_on else None)
        self.crew = Crew(self)
        self._triage_lock = threading.Lock()

    # ---- basics ----------------------------------------------------------------------------------------------------
    def con(self):
        return db.connect(self.s.db_path, restricted=True)

    def clock(self) -> str:
        return (datetime.strptime(self.s.now, TIME_FMT) + self._offset).strftime(TIME_FMT)

    def advance_clock(self, minutes: int) -> str:
        self._offset += timedelta(minutes=minutes)
        return self.clock()

    def next_update_time(self) -> str:
        return (datetime.strptime(self.clock(), TIME_FMT) + timedelta(minutes=60)).strftime("%H:%M")

    def audit(self, actor: str, event: str, detail: str) -> None:
        con = self.con()
        try:
            con.execute("INSERT INTO audit(ts, actor, event, detail) VALUES(?,?,?,?)",
                        (self.clock(), actor, event, guardrails.scrub(detail)[:500]))
            con.commit()
        finally:
            con.close()

    def _page(self, team: str, actor: str) -> str:
        eng = self.cat.oncall[team]["engineer"]
        self.audit(actor, "page_oncall", f"paged {team} on-call ({eng}) by team name; no phone number is used or shown")
        return f"paged the {team} on-call ({eng})"

    def _unsafe_execute(self, name: str, service: str) -> str:
        """Only exists when approvals are switched off for the red-team 'before' run."""
        line = f"{self.clock()} | UNAPPROVED | {name} on {service} | simulated"
        self.s.actions_log.parent.mkdir(parents=True, exist_ok=True)
        with open(self.s.actions_log, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return f"ran {name} on {service} (no approval)"

    # ---- models, metered ---------------------------------------------------------------------------------------------
    def call_llm(self, purpose: str, role: str, system: str, user: str, max_tokens: int = 600) -> tuple[LLMResult, float]:
        if self.model_down:
            raise LLMError("model connection is down")
        if self.s.on("redaction"):  # last door before the model: nothing sensitive goes out even if an earlier step missed it
            red = guardrails.redact(user)
            if red.counts:
                self.metrics.block("prompt_redacted")
            user = red.text
        with self.tracer.span(f"llm.{purpose}", model=self.llm.model_name(role), role=role):
            res = self.llm.complete(system, user, role=role, max_tokens=max_tokens, purpose=purpose)
        cost = self.metrics.model_call(purpose, role, res.tokens_in, res.tokens_out)
        self.log.info("model call", extra={"event": "model_call", "model": res.model, "tokens": res.tokens_in + res.tokens_out,
                                           "ms": round(res.latency_ms), "detail": purpose})
        return res, cost

    # ---- triage -------------------------------------------------------------------------------------------------------
    def starter_alerts(self, con=None) -> list[Alert]:
        c = con or self.con()
        try:
            return [Alert(**{k: r[k] for k in r.keys()}) for r in c.execute("SELECT * FROM alerts ORDER BY time, alert_id")]
        finally:
            if con is None:
                c.close()

    def ingest(self, alerts: list[Alert]) -> None:
        con = self.con()
        try:
            for a in alerts:
                con.execute("INSERT OR IGNORE INTO alerts VALUES(?,?,?,?,?,?,?,?)",
                            (a.alert_id, a.time, a.source, a.service, a.check, a.severity, a.status, a.message))
            con.commit()
        finally:
            con.close()

    def views(self, alerts: list[Alert]) -> list[AlertView]:
        return [guardrails.alert_view(a, self.s.on("input_check"), self.s.on("redaction")) for a in alerts]

    def save(self, con, inc: Incident) -> None:
        con.execute("INSERT OR REPLACE INTO incidents(incident_id, opened, severity, status, root_cause, data, updated) VALUES(?,?,?,?,?,?,?)",
                    (inc.incident_id, inc.opened, inc.severity, inc.status, inc.root_cause, inc.model_dump_json(), self.clock()))

    def get_incident(self, incident_id: str) -> Incident | None:
        con = self.con()
        try:
            row = con.execute("SELECT data FROM incidents WHERE incident_id=?", (incident_id,)).fetchone()
            return Incident.model_validate_json(row["data"]) if row else None
        finally:
            con.close()

    def list_incidents(self) -> list[Incident]:
        con = self.con()
        try:
            return [Incident.model_validate_json(r["data"]) for r in con.execute("SELECT data FROM incidents ORDER BY incident_id")]
        finally:
            con.close()

    def triage_rules(self, universe: list[Alert]) -> list[Incident]:
        return run_triage(universe, self.cat)

    def process(self, universe: list[Alert], with_brief: bool = True, emit=None) -> list[Incident]:
        """Rules first (no model), then the crew on every actionable incident. A person's decision is never overwritten."""
        with self._triage_lock:
            by_id = {a.alert_id: a for a in universe}
            fresh = self.triage_rules(universe)
            out: list[Incident] = []
            con = self.con()
            try:
                stored = {r["incident_id"]: Incident.model_validate_json(r["data"]) for r in con.execute("SELECT incident_id, data FROM incidents")}
            finally:
                con.close()
            for inc in fresh:
                old = stored.get(inc.incident_id)
                if old and old.status in ("CHANGE_DONE", "REJECTED") and old.alert_ids == inc.alert_ids:
                    out.append(old)  # a decision a person made is final
                    continue
                if old and old.alert_ids == inc.alert_ids and old.last_alert == inc.last_alert and old.crew and (
                        old.brief or old.status in ("AUTO_RESOLVED", "NEEDS_PERSON")) and with_brief:
                    out.append(old)  # same alerts: reuse the brief instead of paying for it again
                    continue
                if old and old.request_id and old.alert_ids != inc.alert_ids:
                    c2 = self.con()
                    try:
                        c2.execute("UPDATE action_requests SET status='SUPERSEDED' WHERE request_id=? AND status='PENDING'", (old.request_id,))
                        self.actions.audit(c2, "tower", "request_superseded", f"{old.request_id}: new alerts joined {inc.incident_id}")
                        c2.commit()
                    finally:
                        c2.close()
                inc.alerts = self.views([by_id[i] for i in inc.alert_ids])
                with self.tracer.span("crew", incident=inc.incident_id):
                    self.crew.run(inc, emit=emit, models=with_brief)
                out.append(inc)
                c3 = self.con()
                try:
                    self.save(c3, inc)
                    c3.commit()
                finally:
                    c3.close()
            keep = [i.incident_id for i in out]
            c4 = self.con()
            try:
                if keep:
                    c4.execute(f"DELETE FROM incidents WHERE incident_id NOT IN ({','.join('?' * len(keep))})", keep)
                else:
                    c4.execute("DELETE FROM incidents")
                c4.commit()
            finally:
                c4.close()
            return out

    def triage(self, alerts: list[Alert] | None = None, with_brief: bool = True, emit=None) -> list[Incident]:
        if alerts:
            self.ingest(alerts)
        return self.process(self.starter_alerts(), with_brief, emit)

    def run_crew_on(self, incident_id: str, emit=None) -> Incident | None:
        """Run the crew again on one stored incident (the 'watch the agents work' button)."""
        inc = self.get_incident(incident_id)
        if inc is None or inc.status in ("CHANGE_DONE", "REJECTED"):
            return inc
        con = self.con()
        try:
            universe = {a.alert_id: a for a in self.starter_alerts(con)}
            if inc.request_id:
                con.execute("UPDATE action_requests SET status='SUPERSEDED' WHERE request_id=? AND status='PENDING'", (inc.request_id,))
                con.commit()
        finally:
            con.close()
        fresh = next((i for i in self.triage_rules(list(universe.values())) if i.incident_id == incident_id), None)
        if fresh is None:
            return None
        fresh.alerts = self.views([universe[i] for i in fresh.alert_ids])
        with self.tracer.span("crew", incident=incident_id):
            self.crew.run(fresh, emit=emit, models=True)
        con = self.con()
        try:
            self.save(con, fresh)
            con.commit()
        finally:
            con.close()
        return fresh

    def stream_crew(self, incident_id: str) -> Iterator[dict]:
        """Events for the UI while the crew works: each agent step as it happens, then the finished incident."""
        q: queue.Queue = queue.Queue()
        result: dict = {}

        def work():
            try:
                result["inc"] = self.run_crew_on(incident_id, emit=lambda s: q.put({"type": "step", "step": s}))
            except Exception as e:  # noqa: BLE001
                result["err"] = type(e).__name__
            finally:
                q.put(None)

        threading.Thread(target=work, daemon=True).start()
        while True:
            item = q.get()
            if item is None:
                break
            yield item
        if "err" in result or result.get("inc") is None:
            yield {"type": "error", "error": result.get("err", "no such incident")}
        else:
            yield {"type": "done", "incident": result["inc"].model_dump()}

    # ---- live replay (stretch: alerts arrive one at a time) ------------------------------------------------------------
    def replay_reset(self) -> dict:
        con = self.con()
        try:
            for tbl in ("replay", "incidents", "approvals", "action_requests", "audit"):
                con.execute(f"DELETE FROM {tbl}")
            con.commit()
        finally:
            con.close()
        self._offset = timedelta(0)
        self.cache.clear()
        return {"seen": 0, "total": len(self.starter_alerts())}

    def replay_step(self) -> dict:
        con = self.con()
        try:
            alerts = self.starter_alerts(con)
            seen = {r["alert_id"] for r in con.execute("SELECT alert_id FROM replay")}
            nxt = next((a for a in alerts if a.alert_id not in seen), None)
            if nxt is None:
                return {"done": True, "seen": len(seen), "total": len(alerts)}
            con.execute("INSERT INTO replay(alert_id, seq) VALUES(?,?)", (nxt.alert_id, len(seen) + 1))
            con.commit()
            seen.add(nxt.alert_id)
        finally:
            con.close()
        before = {i.incident_id: len(i.alert_ids) for i in self.list_incidents()}
        universe = [a for a in alerts if a.alert_id in seen]
        incs = self.process(universe, with_brief=False)
        mine = next(i for i in incs if nxt.alert_id in i.alert_ids)
        grew = mine.incident_id in before and len(mine.alert_ids) > before[mine.incident_id]
        return {"done": False, "seen": len(seen), "total": len(alerts), "alert": nxt.model_dump(),
                "incident_id": mine.incident_id, "grew": grew, "new_incident": mine.incident_id not in before,
                "incident_alerts": len(mine.alert_ids)}

    # ---- plain-words status page (stretch) ------------------------------------------------------------------------------
    def status_page(self) -> dict:
        items = []
        for i in self.list_incidents():
            if i.severity not in ("P1", "P2") or i.status in ("AUTO_RESOLVED", "REJECTED"):
                continue
            names = [self.cat.services[s].name for s in i.services if s in self.cat.services]
            fixed = i.status == "CHANGE_DONE"
            items.append({
                "title": ("Resolved: " if fixed else "") + (" and ".join(names[:2]) + (f" and {len(names) - 2} more" if len(names) > 2 else "")),
                "level": "resolved" if fixed else ("outage" if i.severity == "P1" else "degraded"),
                "message": ("A fix has been applied and we are watching that everything is back to normal." if fixed else
                            "Some people may not be able to use these services right now. A fix is ready and is waiting for sign-off by the right people."
                            if i.severity == "P1" else
                            "These services may be slow or unreliable. The team is working on it."),
                "next_update": self.next_update_time(), "since": i.opened,
            })
        return {"as_of": self.clock(), "all_clear": not items, "items": items}

    # ---- escalation by age (stretch) -------------------------------------------------------------------------------------
    def escalate(self, minutes: int = 15) -> list[dict]:
        paged = []
        con = self.con()
        try:
            now = datetime.strptime(self.clock(), TIME_FMT)
            for r in con.execute("SELECT * FROM action_requests WHERE status='PENDING'"):
                age = (now - datetime.strptime(r["created"], TIME_FMT)).total_seconds() / 60
                if age < minutes:
                    continue
                if con.execute("SELECT 1 FROM audit WHERE event='escalated' AND detail LIKE ?", (f"{r['request_id']}%",)).fetchone():
                    continue
                dm = self.cat.duty_manager()
                con.execute("INSERT INTO audit(ts, actor, event, detail) VALUES(?,?,?,?)",
                            (self.clock(), "tower", "page_oncall", f"paged Duty manager ({dm['engineer']}) by team name; no phone number is used or shown"))
                con.execute("INSERT INTO audit(ts, actor, event, detail) VALUES(?,?,?,?)",
                            (self.clock(), "tower", "escalated", f"{r['request_id']} has waited {int(age)} minutes for approval; duty manager paged (policy 5.2)"))
                paged.append({"request_id": r["request_id"], "waited_minutes": int(age), "paged": dm["engineer"]})
            con.commit()
        finally:
            con.close()
        return paged

    # ---- ask --------------------------------------------------------------------------------------------------------------
    def latest_alert(self, question: str) -> str:
        svcs = self.cat.find_services(question)
        con = self.con()
        try:
            if svcs:
                row = con.execute(f"SELECT MAX(time) m FROM alerts WHERE service IN ({','.join('?' * len(svcs))})", svcs).fetchone()
            else:
                row = con.execute("SELECT MAX(time) m FROM alerts").fetchone()
            return row["m"] or ""
        finally:
            con.close()

    def _live_chunks(self) -> list[dict]:
        out = []
        for i in self.list_incidents():
            rec = f"; recommended {i.runbook_id} step {i.recommended_step} ({i.action}) on {i.target}" if i.recommended_step else ""
            alerts = " | ".join(f"{a.alert_id} {a.service} {a.check} {a.severity}: {a.message}" for a in i.alerts)
            out.append({"source": f"{i.incident_id} current", "kind": "incident",
                        "text": f"Incident {i.incident_id} {i.severity or 'no severity'} {i.status.replace('_', ' ').lower()}, root cause "
                                f"{i.root_cause or 'unknown'}, services {', '.join(i.services)}, {i.approvals_needed} approval(s) needed{rec}. "
                                f"Alerts: {alerts}"})
        return out

    def _refusal(self, reasons: list[str], contact: bool = False, q: str = "") -> str:
        if contact:
            team = next((t for t, p in self.cat.oncall.items() if p["engineer"].lower().replace(". ", " ").split()[-1] in q.lower()), None)
            who = f" for {team}" if team else ""
            return ("I never show anyone's personal mobile number (policy 7.3). To reach an on-call engineer, page the team by name: "
                    f"use page_oncall{('(' + team + ')') if team else '(team)'}{who}. Their work email is in the on-call table.")
        return ("I can't act on that message: " + "; ".join(reasons) + ". It looks like an instruction, not a question about the operation. "
                "Ask what you want to know (a status, a runbook, a policy). Changes are never run from here: they need an approved "
                "request for one step on one service.")

    def ask(self, question: str) -> askmod.AskResult:
        t0 = time.perf_counter()
        with self.tracer.span("ask", question=question[:120]) as sp:
            r = self._ask(question.strip(), sp)
        r.ms = (time.perf_counter() - t0) * 1000
        self.metrics.route(r.route, r.ms, r.ttft_ms)
        return r

    def _ask(self, q: str, sp) -> askmod.AskResult:
        if self.s.on("input_check"):
            with self.tracer.span("guard.input"):
                v = guardrails.check_input(q, "question")
            if v.flagged:
                self.metrics.block("input")
                self.audit("operator", "question_blocked", f"{'; '.join(v.reasons)}: {q[:150]}")
                return askmod.AskResult(self._refusal(v.reasons), route="blocked", blocked=True, reasons=v.reasons)
            if guardrails.asks_for_personal_contact(q):
                self.metrics.block("personal_contact")
                return askmod.AskResult(self._refusal([], contact=True, q=q), route="blocked", blocked=True,
                                        reasons=["asks for a personal mobile (policy 7.3)"], sources=["policy 7.3"])
        route = askmod.classify(q, self.s.routing)
        sp["attrs"]["route"] = route
        if route == "data":
            with self.tracer.span("route.data"):
                con = self.con()
                try:
                    hit = askmod.data_answer(q, self.cat, con, self.clock())
                finally:
                    con.close()
            if hit:
                text, sources = hit
                if self.s.on("output_check"):
                    text = guardrails.check_output(text).text
                return askmod.AskResult(text, sources, route="data", model="none")
            route = "large"
        role = "small" if route == "small" else "large"
        model = self.llm.model_name(role)
        key = askmod.AnswerCache.key(q, model, self.latest_alert(q))
        if self.s.cache:
            hit = self.cache.get(key)
            self.metrics.cache_event(hit is not None)
            if hit is not None:
                with self.tracer.span("cache.hit"):
                    return askmod.AskResult(**{**hit.as_dict(), "route": "cache", "cached": True, "cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0})
        with self.tracer.span("retrieve"):
            chunks = self._retrieve(q)
        try:
            res, cost = self.call_llm("ask", role, prompts.SYSTEM_ASK, prompts.ask_user(q, chunks), 400)
        except LLMError as e:
            self.metrics.block("model_error")
            return askmod.AskResult(f"The model is not reachable right now ({e}). Status and fact questions still work.",
                                    route=route, blocked=True, reasons=["model unavailable"])
        text, tools = self._tools_and_check(res.text)
        r = askmod.AskResult(text, [c["source"] for c in chunks][:5], route=route, model=res.model, tokens_in=res.tokens_in,
                             tokens_out=res.tokens_out, cost_usd=cost, tools=tools, ttft_ms=res.ttft_ms)
        if self.s.cache:
            self.cache.put(key, r)
        return r

    def _retrieve(self, q: str) -> list[dict]:
        chunks = self.index.search(q, k=7, extra=self._live_chunks())
        safe = []
        for c in chunks:  # runbook and incident text is checked before a model reads it
            if self.s.on("input_check") and guardrails.check_input(c["text"], "alert").flagged:
                self.metrics.block("chunk")
                continue
            safe.append({**c, "text": guardrails.redact(c["text"]).text} if self.s.on("redaction") else c)
        return safe

    def _tools_and_check(self, text: str) -> tuple[str, list[str]]:
        notes, used = [], []
        for name, arg in parse_calls(text):
            tr = self.gateway.call(name, service=arg, actor="model")
            used.append(f"{name}({arg}): {'ok' if tr.ok else 'refused'}")
            notes.append(f"[{name}] {tr.text}")
        clean = re.sub(r"\bCALL\s+[a-z_]+\([^)]*\)", "", text).strip()
        if notes:
            clean += "\n\n" + "\n".join(notes)
        if self.s.on("output_check"):
            ov = guardrails.check_output(clean, prompts.PROTECTED)
            if not ov.ok:
                self.metrics.block("output")
                self.audit("tower", "answer_checked", "; ".join(ov.reasons))
            clean = ov.text
        return clean, used

    def ask_stream(self, question: str) -> Iterator[dict]:
        """Events: meta, chunk (only text that has passed the output check), replace (answer withdrawn), done."""
        q = question.strip()
        t0 = time.perf_counter()
        # everything except the model call itself behaves as in ask(); only model routes stream
        if self.s.on("input_check"):
            v = guardrails.check_input(q, "question")
            if v.flagged or guardrails.asks_for_personal_contact(q):
                r = self.ask(q)
                yield {"type": "meta", "route": r.route}
                yield {"type": "chunk", "text": r.answer}
                yield {"type": "done", **r.as_dict()}
                return
        route = askmod.classify(q, self.s.routing)
        if route == "data":
            r = self.ask(q)
            yield {"type": "meta", "route": r.route}
            yield {"type": "chunk", "text": r.answer}
            yield {"type": "done", **r.as_dict()}
            return
        role = "small" if route == "small" else "large"
        key = askmod.AnswerCache.key(q, self.llm.model_name(role), self.latest_alert(q))
        if self.s.cache:
            hit = self.cache.get(key)
            self.metrics.cache_event(hit is not None)
            if hit is not None:
                ms = (time.perf_counter() - t0) * 1000
                self.metrics.route("cache", ms, None, ms)
                yield {"type": "meta", "route": "cache"}
                yield {"type": "chunk", "text": hit.answer}
                yield {"type": "done", **{**hit.as_dict(), "route": "cache", "cached": True, "cost_usd": 0.0, "ms": ms}}
                return
        yield {"type": "meta", "route": route, "model": self.llm.model_name(role)}
        chunks = self._retrieve(q)
        if self.model_down:
            yield {"type": "done", "answer": "The model is not reachable right now.", "route": route, "blocked": True}
            return
        buf, shown, first_visible, res, withdrawn = "", 0, None, None, False
        with self.tracer.span("llm.ask.stream", model=self.llm.model_name(role)):
            try:
                for kind, payload in self.llm.stream(prompts.SYSTEM_ASK, prompts.ask_user(q, chunks), role=role, max_tokens=400, purpose="ask"):
                    if kind == "chunk":
                        buf += payload
                        cut = askmod.sentence_release(buf)
                        if cut > shown and not withdrawn:
                            seg_ok = True
                            seg = buf[shown:cut]
                            if self.s.on("output_check"):
                                ov = guardrails.check_output(buf[:cut], prompts.PROTECTED)
                                seg_ok = ov.ok or all("secret or personal" in r for r in ov.reasons)
                                seg = guardrails.check_output(seg).text if seg_ok else ""
                                if not seg_ok:
                                    withdrawn = True
                                    self.metrics.block("output")
                                    yield {"type": "replace", "text": ov.text}
                            if seg_ok:
                                seg = re.sub(r"\bCALL\s+[a-z_]+\([^)]*\)", "", seg)
                                if first_visible is None:
                                    first_visible = (time.perf_counter() - t0) * 1000
                                shown = cut
                                yield {"type": "chunk", "text": seg}
                    else:
                        res = payload
            except LLMError as e:
                yield {"type": "done", "answer": f"The model is not reachable right now ({e}).", "route": route, "blocked": True}
                return
        cost = self.metrics.model_call("ask", role, res.tokens_in, res.tokens_out)
        final, tools = self._tools_and_check(res.text)
        if not withdrawn and len(buf) > shown:
            tail = re.sub(r"\bCALL\s+[a-z_]+\([^)]*\)", "", buf[shown:])
            if self.s.on("output_check"):
                tail = guardrails.check_output(tail).text
            if first_visible is None:
                first_visible = (time.perf_counter() - t0) * 1000
            yield {"type": "chunk", "text": tail}
        ms = (time.perf_counter() - t0) * 1000
        r = askmod.AskResult(final, [c["source"] for c in chunks][:5], route=route, model=res.model, tokens_in=res.tokens_in,
                             tokens_out=res.tokens_out, cost_usd=cost, ms=ms, ttft_ms=res.ttft_ms, tools=tools)
        if self.s.cache and not withdrawn:
            self.cache.put(key, r)
        self.metrics.route(route, ms, res.ttft_ms, first_visible)
        yield {"type": "done", **r.as_dict(), "first_visible_ms": first_visible}

    # ---- health ------------------------------------------------------------------------------------------------------------
    def ready(self) -> dict:
        checks = {}
        try:
            con = self.con()
            checks["database"] = con.execute("SELECT COUNT(*) FROM services").fetchone()[0] > 0
            con.close()
        except Exception:  # noqa: BLE001
            checks["database"] = False
        checks["runbook_index"] = self.index.size() > 0 and len(self.cat.runbooks) == 8
        checks["model"] = (not self.model_down) and bool(self.llm.ping())
        return {"ready": all(checks.values()), "checks": checks}
