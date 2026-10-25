"""Operations Control Tower: the screen. Calls the API only. Tabs: Incidents, Incident, Ask the tower, Health & cost,
and the Project03 extras: Agent crew, Live replay, Status page.

    streamlit run ui/app.py        (the API must be running: uvicorn tower.api:create_app --factory)
"""
from __future__ import annotations

import csv
import html
import json
import os
import re
import time
from pathlib import Path

import requests
import streamlit as st

API = os.environ.get("TOWER_API", "http://127.0.0.1:8000")
ROOT = Path(__file__).resolve().parent.parent
PHOENIX = os.environ.get("PHOENIX_URL", "http://localhost:6006")

st.set_page_config(page_title="Operations Control Tower", page_icon="🗼", layout="wide")

CSS = """
<style>
:root { --navy:#1b1f3b; --amber:#f5a623; --teal:#0f9d8a; --red:#d64545; --blue:#3b6fd4; --grey:#6b7280; --soft:#f3f4fa; }
.block-container { padding-top: 3.6rem; }
.band { background: var(--navy); color:#fff; padding: 14px 20px; border-radius: 8px; display:flex; justify-content:space-between; align-items:center; margin-bottom: 12px; }
.band h2 { margin:0; font-size: 1.25rem; color:#fff; } .band small { color:#c9cbe0; }
.chip { display:inline-block; padding:2px 9px; border-radius:11px; font-size:.72rem; font-weight:600; letter-spacing:.02em; white-space:nowrap; }
.sev-P1 { background:#d64545; color:#fff; } .sev-P2 { background:#e8833a; color:#fff; } .sev-P3 { background:#e9c24a; color:#3a2f00; } .sev-P4 { background:#cdd1da; color:#333; }
.st-WAITING_FOR_APPROVAL { background:#dbe6fb; color:#1c3f8f; } .st-NEEDS_PERSON { background:#fde0e0; color:#a42626; } .st-AUTO_RESOLVED { background:#d9f2ec; color:#0a6b5c; }
.st-CHANGE_DONE { background:#c8efe6; color:#075a4c; } .st-REJECTED { background:#e5e7eb; color:#444; }
.k-rules { background:#e6e8f5; color:#2b3170; } .k-model { background:#fdebc8; color:#7a4b00; } .k-model\\+tools, .k-tool { background:#fbe0b8; color:#7a3b00; } .k-people { background:#d9f2ec; color:#0a6b5c; }
table.inc { width:100%; border-collapse:collapse; font-size:.86rem; } table.inc th { text-align:left; color:var(--grey); font-size:.7rem; letter-spacing:.06em; padding:6px 8px; border-bottom:2px solid #e5e7eb; }
table.inc td { padding:9px 8px; border-bottom:1px solid #eceef5; vertical-align:top; }
.tile { background:var(--soft); border-radius:8px; padding:12px 14px; height:100%; } .tile .lbl { font-size:.68rem; color:var(--grey); letter-spacing:.06em; text-transform:uppercase; }
.tile .val { font-size:1.7rem; font-weight:700; color:var(--navy); line-height:1.2; } .tile .sub { font-size:.74rem; color:var(--grey); }
.card { border:1px solid #e3e5f0; border-radius:8px; padding:10px 14px; margin-bottom:8px; background:#fff; }
.step { border-left:4px solid #c9cbe0; padding:6px 12px; margin:6px 0; background:#fafbff; border-radius:0 6px 6px 0; } .step.rules { border-color:#5b64c9; } .step.model, .step.model\\+tools, .step.tool { border-color:var(--amber); }
.step.people { border-color:var(--teal); } .step.fail { border-color:var(--red); background:#fff5f5; } .step.stop { border-color:var(--red); }
.agent { font-weight:700; color:var(--navy); } .meta { color:var(--grey); font-size:.74rem; }
.notice { background:#eef6ff; border:1px solid #bcd7f7; border-radius:8px; padding:8px 12px; font-size:.82rem; color:#1c3f6b; }
.bar { height:14px; border-radius:7px; background:#e8eaf3; overflow:hidden; display:flex; } .bar div { height:100%; }
.warn { background:#fff4e0; border:1px solid #f1c27d; border-radius:8px; padding:8px 12px; font-size:.82rem; color:#6b4300; }
.mono { font-family: ui-monospace, Menlo, Consolas, monospace; font-size:.8rem; }
.status-card { border-radius:10px; padding:14px 18px; margin:10px 0; border:1px solid #e3e5f0; } .lv-outage { background:#fdeaea; border-color:#f0b4b4; } .lv-degraded { background:#fff4e0; border-color:#f1c27d; } .lv-resolved { background:#e4f6f1; border-color:#9fd8c9; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------------------------------------------------
def get(path: str, **params):
    try:
        r = requests.get(API + path, params=params, timeout=30)
        return r.json() if r.status_code == 200 else None
    except requests.RequestException:
        return None


def post(path: str, body: dict | None = None, **params):
    try:
        r = requests.post(API + path, json=body if body is not None else {}, params=params, timeout=600)
        return r.status_code, (r.json() if r.content else {})
    except requests.RequestException as e:
        return 0, {"detail": f"cannot reach the API at {API} ({type(e).__name__})"}


def chip(text: str, cls: str) -> str:
    return f'<span class="chip {cls}">{html.escape(text)}</span>'


def sev_chip(s):
    return chip(s, f"sev-{s}") if s else chip("--", "sev-P4")


def status_chip(s):
    return chip(s.replace("_", " "), f"st-{s}")


def band(title: str, right: str = "") -> None:
    st.markdown(f'<div class="band"><h2>{title}</h2><small>{right}</small></div>', unsafe_allow_html=True)


def tile(label: str, value: str, sub: str = "") -> str:
    return f'<div class="tile"><div class="lbl">{label}</div><div class="val">{value}</div><div class="sub">{sub}</div></div>'


def when(ts: str) -> str:
    try:
        t = time.strptime(ts, "%Y-%m-%d %H:%M")
        return time.strftime("%a %H:%M", t)
    except ValueError:
        return ts


def next_step(i: dict) -> str:
    if i["status"] == "NEEDS_PERSON":
        return "page the duty manager" if not i.get("root_cause") else "a person decides: " + (i.get("needs_person_reason") or "")[:60]
    if i["status"] == "AUTO_RESOLVED":
        return "none: cleared by itself"
    if i["status"] == "CHANGE_DONE":
        return f"done: {i.get('action')} on {i.get('target')} (simulated)"
    if i.get("recommended_step"):
        return f"{i['runbook_id']} step {i['recommended_step']} · {i['action']}"
    return "crew has not run yet"


# ---- state ------------------------------------------------------------------------------------------------------------
ready = get("/ready")
if ready is None and get("/health") is None:
    st.error(f"The tower API is not reachable at {API}. Start it with `uvicorn tower.api:create_app --factory --port 8000`, or `docker compose up`.")
    st.stop()
health = get("/health") or {}
metrics = get("/metrics") or {}
incidents = get("/incidents") or []
settings = metrics.get("settings", {})
st.session_state.setdefault("selected", incidents[0]["incident_id"] if incidents else None)
if st.query_params.get("incident") and st.session_state.get("_deep_link") != st.query_params["incident"]:
    st.session_state.selected = st.query_params["incident"]  # a link like ?incident=INC-3008 opens that incident
    st.session_state["_deep_link"] = st.query_params["incident"]

with st.sidebar:
    st.markdown("### 🗼 Operations Control Tower")
    st.caption("Alerts in · a person approves every change")
    open_ = [i for i in incidents if i["status"] in ("WAITING_FOR_APPROVAL", "NEEDS_PERSON")]
    st.markdown("**OPEN NOW**")
    c = st.columns(2)
    for sev in ("P1", "P2", "P3"):
        n = sum(1 for i in open_ if i["severity"] == sev)
        c[0].markdown(sev_chip(sev), unsafe_allow_html=True)
        c[1].markdown(f"**{n}**")
    c[0].write("Needs a person")
    c[1].markdown(f"**{sum(1 for i in open_ if i['status'] == 'NEEDS_PERSON')}**")
    c[0].write("Waiting for approval")
    c[1].markdown(f"**{sum(1 for i in open_ if i['status'] == 'WAITING_FOR_APPROVAL')}**")
    st.markdown("**SETTINGS**")
    st.markdown(f"Guardrails {chip('ON' if settings.get('guardrails') else 'OFF', 'st-AUTO_RESOLVED' if settings.get('guardrails') else 'st-NEEDS_PERSON')}", unsafe_allow_html=True)
    st.markdown(f"Changes {chip('APPROVAL ONLY' if settings.get('approvals_enforced') else 'UNSAFE', 'st-WAITING_FOR_APPROVAL' if settings.get('approvals_enforced') else 'st-NEEDS_PERSON')}", unsafe_allow_html=True)
    st.markdown(f"Change freeze {chip('ACTIVE until Mon 06:00' if (settings.get('clock', '') >= '2026-10-23 18:00' and settings.get('clock', '') < '2026-10-26 06:00') else 'not active', 'sev-P3')}", unsafe_allow_html=True)
    st.caption(f"Model (brief): `{settings.get('llm_model', '?')}`  \nModel (lookups): `{settings.get('small_model', '?')}`  \nTower clock: {settings.get('clock', '?')}")
    sc = (get("/scenarios/score") or {}).get("summary")
    if sc:
        st.markdown("**SCENARIOS (10)**")
        for label, key in (("Grouping right", "grouping"), ("Root cause right", "root_cause"), ("Severity right", "severity"),
                           ("Approvals right", "approvals"), ("Runbook step right", "runbook_step")):
            st.markdown(f"{label}: **{sc[key]}/10**")
    st.divider()
    if st.button("▶ Triage the 22 starter alerts", use_container_width=True, type="primary"):
        with st.spinner("Rules group the alerts, then the crew briefs each incident…"):
            code, out = post("/triage", {})
        st.success(f"{out.get('alerts', '?')} alerts → {out.get('count', '?')} incidents") if code == 200 else st.error(out.get("detail", "failed"))
        st.rerun()
    st.markdown(f'<div class="notice">🤖 This tower uses AI to write briefs and answers. A person approves every change.</div>', unsafe_allow_html=True)

tabs = st.tabs(["Incidents", "Incident", "Ask the tower", "Health & cost", "🤖 Agent crew", "⏱ Live replay", "📣 Status page"])

# ---- 1. Incidents ----------------------------------------------------------------------------------------------------------
with tabs[0]:
    band("Incidents", f"{settings.get('clock', '')} · {sum(len(i['alert_ids']) for i in incidents)} alerts grouped into {len(incidents)} incidents")
    if not incidents:
        st.info("No incidents yet. Press **Triage the 22 starter alerts** in the sidebar.")
    else:
        rows = []
        for i in sorted(incidents, key=lambda x: x["incident_id"], reverse=True):
            rc = i["root_cause"] or '<i>not in catalogue</i>'
            if i.get("root_cause") and i["services"] and len(i["services"]) > 1:
                rc += f' <span class="meta">(+{len(i["services"]) - 1} affected)</span>'
            flags = " · ".join(html.escape(f) for f in i["flags"])
            rows.append(f"<tr><td class='mono'>{i['incident_id']}</td><td>{sev_chip(i['severity'])}</td><td>{rc}</td><td>{len(i['alert_ids'])}</td>"
                        f"<td>{when(i['opened'])}</td><td>{status_chip(i['status'])}</td><td>{html.escape(next_step(i))}</td><td class='meta'>{flags}</td></tr>")
        st.markdown("<table class='inc'><tr><th>INCIDENT</th><th>SEV</th><th>ROOT CAUSE</th><th>ALERTS</th><th>OPENED</th><th>STATUS</th><th>NEXT STEP</th><th>FLAGS</th></tr>"
                    + "".join(rows) + "</table>", unsafe_allow_html=True)
        st.write("")
        pick = st.selectbox("Open an incident", [i["incident_id"] for i in incidents],
                            index=[i["incident_id"] for i in incidents].index(st.session_state.selected) if st.session_state.selected in [i["incident_id"] for i in incidents] else 0)
        st.session_state.selected = pick
        st.caption("Then open the **Incident** tab for the alerts, the runbook step, the evidence and the approval panel.")

# ---- 2. Incident -------------------------------------------------------------------------------------------------------------
with tabs[1]:
    inc = get(f"/incidents/{st.session_state.selected}") if st.session_state.selected else None
    if not inc:
        st.info("Pick an incident in the Incidents tab.")
    else:
        title = (re.split(r"(?<=[.!?])\s", inc["brief"]["summary"].strip())[0] if inc.get("brief") else f"{inc['root_cause'] or 'Unknown service'}")
        band(f"{inc['incident_id']} · {html.escape(title[:90])}", f"opened {when(inc['opened'])} · {len(inc['alert_ids'])} alert(s)")
        left, right = st.columns([3, 2])
        with left:
            st.markdown(f"{sev_chip(inc['severity'])} {status_chip(inc['status'])} root cause **{inc['root_cause'] or 'unknown'}** "
                        f"{chip('CHANGE FREEZE (policy 5.3)', 'sev-P2') if inc['freeze'] else ''}", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown("**Alerts, as the model and the log see them**  <span class='meta'>secrets and personal data hidden before any model call (policy 7.2)</span>", unsafe_allow_html=True)
                for a in inc["alerts"]:
                    st.markdown(f"<span class='mono'><b>{a['alert_id']}</b> · {a['time'][11:]} · {a['service']} · {a['severity']} · {a['check']}</span>", unsafe_allow_html=True)
                    msg = html.escape(a["message"]).replace("&lt;SECRET&gt;", "<span class='chip st-NEEDS_PERSON'>SECRET</span>").replace("&lt;UK_MOBILE&gt;", "<span class='chip st-NEEDS_PERSON'>UK_MOBILE</span>")
                    st.markdown(f"<div class='mono' style='margin:0 0 6px 8px'>{msg}</div>", unsafe_allow_html=True)
                    if a["flagged"]:
                        st.markdown(f"<div class='warn'>⚠ <b>Instructions in alert text were ignored.</b> {html.escape('; '.join(a['flag_reasons']))}. "
                                    "The text was withheld from the model. The tower treats it as data, never as an order (policy 7.1).</div>", unsafe_allow_html=True)
                        with st.expander("Show the original text (inert, quoted, secrets still hidden)"):
                            st.code(a["original_shown"] or "", language=None)
            if inc["reads"]:
                with st.container(border=True):
                    st.markdown("**Runbook steps already run** <span class='meta'>[READ] steps only look · simulated readings</span>", unsafe_allow_html=True)
                    for r in inc["reads"]:
                        st.markdown(f"{chip('READ', 'k-rules')} **{r['step']}** · `{r['tool']}` — {html.escape(r['result'])}", unsafe_allow_html=True)
                    b = inc.get("brief")
                    if b and b.get("recommended_change"):
                        rc_ = b["recommended_change"]
                        sim = f" · like {inc['similar_incident']}" if inc.get("similar_incident") else ""
                        st.markdown(f"{chip('CHANGE', 'sev-P2')} **{rc_['runbook_id']} step {rc_['step_no']} · {rc_['action']}** on **{rc_['target_service']}** — recommended{sim}", unsafe_allow_html=True)
                        st.caption(b.get("reason", ""))
            if inc.get("needs_person_reason"):
                st.markdown(f"<div class='warn'><b>A person needs to look at this.</b> {html.escape(inc['needs_person_reason'])}</div>", unsafe_allow_html=True)
            if inc.get("brief") and inc["brief"].get("status_update"):
                with st.container(border=True):
                    st.markdown(f"**Status update draft** <span class='meta'>{inc['severity']}: a person sends it (policy 8.1)</span>", unsafe_allow_html=True)
                    st.write(inc["brief"]["status_update"])
        with right:
            with st.container(border=True):
                st.markdown(f"**Approvals** <span class='meta'>{inc['approvals_needed']} needed · {'two different people' if inc['approvals_needed'] > 1 else 'the owning team'}</span>", unsafe_allow_html=True)
                req = get(f"/actions/{inc['request_id']}") if inc.get("request_id") else None
                if not req:
                    st.caption("No approval is needed for this incident." if inc["approvals_needed"] == 0 else "No request is open yet. Run the crew.")
                else:
                    done = {a["approver"]: a for a in req["approvals"] if a["decision"] == "approve"}
                    for a in inc["approvers"]:
                        ok = a["engineer"] in done
                        st.markdown(f"**{a['engineer']}** · {a['team']}  \n<span class='meta'>{a['why']}</span> "
                                    f"{chip('APPROVED ' + done[a['engineer']]['ts'][11:], 'st-AUTO_RESOLVED') if ok else chip('WAITING', 'st-WAITING_FOR_APPROVAL')}", unsafe_allow_html=True)
                    st.caption("One approval covers one step on one service. " + ("Nothing has changed yet." if req["status"] == "PENDING" else ""))
                    if req["status"] == "CHANGE_DONE":
                        st.success(f"Executed once (simulated): {req['action']} on {req['target_service']}")
                    elif req["status"] == "REJECTED":
                        st.warning("Rejected. Nothing ran.")
                    elif req["status"] == "PENDING":
                        waiting = req["waiting_for"]
                        who = st.selectbox("Approving as", waiting, key=f"who_{req['request_id']}")
                        reason = st.text_input("Reason" + (" (required during the change freeze)" if inc["freeze"] else " (optional)"), key=f"why_{req['request_id']}")
                        b1, b2 = st.columns(2)
                        if b1.button("Approve", type="primary", key=f"ap_{req['request_id']}", use_container_width=True):
                            code, out = post(f"/actions/{req['request_id']}/decide", {"approver": who, "decision": "approve", "reason": reason})
                            (st.error(out.get("detail", "refused")) if code != 200 else st.rerun())
                        if b2.button("Reject", key=f"rj_{req['request_id']}", use_container_width=True):
                            post(f"/actions/{req['request_id']}/decide", {"approver": who, "decision": "reject", "reason": reason})
                            st.rerun()
            with st.container(border=True):
                st.markdown("**Evidence** <span class='meta'>every claim has a source</span>", unsafe_allow_html=True)
                for r in inc["rules_applied"]:
                    st.markdown(f"<span class='mono'>{html.escape(r)}</span>", unsafe_allow_html=True)
            with st.container(border=True):
                hid_s = sum(a["hidden"].get("secrets", 0) for a in inc["alerts"])
                hid_p = sum(a["hidden"].get("personal", 0) for a in inc["alerts"])
                flagged = sum(1 for a in inc["alerts"] if a["flagged"])
                st.markdown("**Guardrails on this incident**")
                st.markdown(f"Secrets hidden: **{hid_s}** · Personal data hidden: **{hid_p}** · Instructions in text: **{flagged}**")
                steps = inc.get("crew", [])
                calls = [s for s in steps if s["model"]]
                st.markdown("**This incident so far**")
                st.markdown(f"Model calls: **{len(calls)}** · Tokens: **{sum(s['tokens'] for s in calls):,}** · Cost: **${sum(s['cost_usd'] for s in calls):.4f}** · "
                            f"Time in models: **{sum(s['ms'] for s in calls) / 1000:.1f} s**")
            log = (get("/actions-log") or {}).get("lines", [])
            if log:
                with st.expander(f"Actions log ({len(log)} line(s), simulated)"):
                    st.code("\n".join(log), language=None)
            if req and req["status"] == "PENDING":
                with st.expander("Escalation by age (demo)"):
                    st.caption("An incident waiting more than 15 minutes pages the duty manager by team name, and the page is audited.")
                    if st.button("Advance the tower clock 20 minutes"):
                        post("/admin/clock", minutes=20)
                    if st.button("Run escalation check"):
                        _, out = post("/escalations/run")
                        st.json(out)

# ---- 3. Ask the tower ------------------------------------------------------------------------------------------------------------
with tabs[2]:
    band("Ask the tower", "answers cite the policy, runbooks, catalogue and past incidents")
    st.markdown('<div class="notice">🤖 You are talking to an AI assistant (EU AI Act Article 50). It answers from the documents and cites them. '
                'It cannot run changes: those need an approved request.</div>', unsafe_allow_html=True)
    try:
        samples = [r["question"] for r in csv.DictReader(open(ROOT / "data" / "operator_questions.csv", encoding="utf-8"))]
    except OSError:
        samples = []
    c1, c2 = st.columns([3, 2])
    q_text = c1.text_input("Your question", key="q_text", placeholder="What is the status of the Payment Portal?")
    q_pick = c2.selectbox("…or pick one", [""] + samples, key="q_pick")
    question = q_text or q_pick
    if st.button("Ask", type="primary", disabled=not question):
        meta: dict = {}

        def gen():
            try:
                with requests.post(API + "/ask/stream", json={"question": question}, stream=True, timeout=120) as r:
                    for line in r.iter_lines():
                        if not line:
                            continue
                        ev = json.loads(line)
                        if ev["type"] == "meta":
                            meta.update(ev)
                        elif ev["type"] == "chunk":
                            yield ev["text"]
                        elif ev["type"] == "replace":
                            yield "\n\n*(answer withdrawn by the output check)*\n\n" + ev["text"]
                        elif ev["type"] == "done":
                            meta.update(ev)
            except requests.RequestException as e:
                yield f"Could not reach the API ({type(e).__name__})."

        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            st.write_stream(gen())
            route = meta.get("route", "?")
            colour = {"data": "st-AUTO_RESOLVED", "small": "sev-P3", "large": "sev-P2", "cache": "k-rules", "blocked": "st-NEEDS_PERSON"}.get(route, "sev-P4")
            bits = [chip(f"route: {route}", colour)]
            if meta.get("model") and meta["model"] != "none":
                bits.append(chip(meta["model"], "k-model"))
            if meta.get("cached"):
                bits.append(chip("from cache", "k-rules"))
            st.markdown(" ".join(bits) + f" <span class='meta'>· {meta.get('ms', 0) / 1000:.2f} s · ${meta.get('cost_usd', 0):.5f} · "
                        f"tokens {meta.get('tokens_in', 0)}→{meta.get('tokens_out', 0)}"
                        + (f" · first words after {meta['first_visible_ms'] / 1000:.2f} s" if meta.get("first_visible_ms") else "") + "</span>", unsafe_allow_html=True)
            if meta.get("blocked") and meta.get("reasons"):
                st.markdown(f"<div class='warn'>Blocked by a guardrail: {html.escape('; '.join(meta['reasons']))}</div>", unsafe_allow_html=True)
            if meta.get("sources"):
                st.caption("Sources: " + " · ".join(meta["sources"]))

# ---- 4. Health & cost -----------------------------------------------------------------------------------------------------------
with tabs[3]:
    band("Health & cost", "before and after Part 2; red team before and after Part 3")
    rd = (ready or {}).get("checks", {})
    c = st.columns(4)
    c[0].markdown(tile("/health", "OK" if health else "DOWN", f"v{health.get('version', '?')} · {health.get('model_mode', '')}"), unsafe_allow_html=True)
    c[1].markdown(tile("/ready", "READY" if (ready or {}).get("ready") else "NOT READY", " · ".join(f"{k} {'✓' if v else '✗'}" for k, v in rd.items())), unsafe_allow_html=True)
    c[2].markdown(tile("Requests / errors", f"{metrics.get('requests_total', 0)} / {metrics.get('errors_total', 0)}", f"model calls {metrics.get('model_calls_total', 0)}"), unsafe_allow_html=True)
    c[3].markdown(tile("Traces", "Phoenix", f"<a href='{PHOENIX}' target='_blank'>{PHOENIX}</a>"), unsafe_allow_html=True)
    st.write("")
    base = get("/reports/perf_real_baseline") or get("/reports/perf_fake_baseline")
    after = get("/reports/perf_real_after") or get("/reports/perf_fake_after")
    ask = metrics.get("ask_latency_ms", {})

    def delta(a, b, unit="s", div=1000.0, money=False):
        if not (a and b):
            return ""
        pct = (b - a) / a * 100 if a else 0
        was = f"${a:.2f}" if money else f"{a / div:.1f} {unit}"
        return f"was {was} · {pct:+.0f}%"

    c = st.columns(5)
    if after:
        c[0].markdown(tile("P50 answer time", f"{after['p50_ms'] / 1000:.2f} s", delta(base and base['p50_ms'], after['p50_ms'])), unsafe_allow_html=True)
        c[1].markdown(tile("P95 answer time", f"{after['p95_ms'] / 1000:.2f} s", delta(base and base['p95_ms'], after['p95_ms'])), unsafe_allow_html=True)
        c[2].markdown(tile("Cost per 1,000 questions", f"${after['cost_per_1000_usd']:.2f}", delta(base and base['cost_per_1000_usd'], after['cost_per_1000_usd'], money=True)), unsafe_allow_html=True)
        c[3].markdown(tile("Cost per incident brief", f"${after['cost_per_brief_usd']:.4f}", f"{after['briefs']} briefs"), unsafe_allow_html=True)
        c[4].markdown(tile("Cache hit rate", f"{after['cache_hit_rate'] * 100:.0f}%", f"TTL {settings.get('cache_ttl_s', 60):.0f} s · key has prompt version"), unsafe_allow_html=True)
    else:
        c[0].markdown(tile("P50 answer time", f"{ask.get('p50', 0) / 1000:.2f} s", "live, since start"), unsafe_allow_html=True)
        c[1].markdown(tile("P95 answer time", f"{ask.get('p95', 0) / 1000:.2f} s", "live, since start"), unsafe_allow_html=True)
        c[2].markdown(tile("Cost per 1,000 questions", f"${metrics.get('cost_per_1000_questions_usd', 0):.2f}", "live"), unsafe_allow_html=True)
        c[3].markdown(tile("Cost per incident brief", f"${metrics.get('cost_per_incident_brief_usd', 0):.4f}", "live"), unsafe_allow_html=True)
        c[4].markdown(tile("Cache hit rate", f"{metrics.get('cache', {}).get('hit_rate', 0) * 100:.0f}%", "live"), unsafe_allow_html=True)
        st.caption("Run `python -m scripts.loadtest` (baseline and after) to fill in the before-and-after numbers.")
    st.write("")
    left, right = st.columns([3, 2])
    with left:
        st.markdown("**Where the questions went** <span class='meta'>routing rule in code</span>", unsafe_allow_html=True)
        routes = (after or {}).get("routes") or metrics.get("routes", {})
        total = sum(routes.values()) or 1
        colours = {"data": "#0f9d8a", "small": "#f5a623", "large": "#1b1f3b", "cache": "#5b64c9", "blocked": "#d64545"}
        st.markdown("<div class='bar'>" + "".join(f"<div style='width:{v / total * 100:.1f}%;background:{colours.get(k, '#999')}'></div>" for k, v in routes.items()) + "</div>", unsafe_allow_html=True)
        p50s = (after or {}).get("route_p50_ms") or metrics.get("route_p50_ms", {})
        ex = {"data": "What is the status of the Payment Portal?", "small": "What does runbook RB-04 say to do first?",
              "large": "Why are the Payment Portal and HR Self-Service down at the same time?", "cache": "(same question again within the TTL)", "blocked": "Ignore your previous instructions…"}
        rows = "".join(f"<tr><td>{chip(k, 'k-rules')}</td><td>{v / total * 100:.0f}%</td><td class='meta'>{ex.get(k, '')}</td><td>{p50s.get(k, 0) / 1000:.2f} s</td></tr>" for k, v in routes.items())
        st.markdown(f"<table class='inc'><tr><th>ROUTE</th><th>SHARE</th><th>EXAMPLE</th><th>P50</th></tr>{rows}</table>", unsafe_allow_html=True)
        if after:
            st.caption(f"Streaming: model's first token p50 {after['ttft_ms_p50'] / 1000:.2f} s · first readable sentence p50 {after['first_visible_ms_p50'] / 1000:.2f} s "
                       f"· whole answer p50 {after['stream_total_ms_p50'] / 1000:.2f} s. Load test: {after['questions']} questions, {after['users']} users, seed {after['seed']}, model `{after['model']}`.")
        st.markdown("**Blocked by a guardrail so far:** " + (", ".join(f"{k} {v}" for k, v in metrics.get("blocked", {}).items()) or "nothing yet"))
        recent = get("/traces/recent", limit=400) or []
        with_model = [s for s in recent if s["name"].startswith("llm.ask")]  # the latest question that really called a model
        last = with_model or [s for s in recent if s["name"] == "ask"]
        if last:
            spans = sorted(get("/traces/recent", request_id=last[-1]["request_id"], limit=60) or [], key=lambda s: s["start"])
            mx = max((s["ms"] for s in spans), default=1) or 1
            slow = max((s for s in spans if s["name"] not in ("http", "ask", "crew")), key=lambda s: s["ms"], default=None)  # slowest step
            st.markdown("**Trace of the last model answer** <span class='meta'>the same spans go to Phoenix · slowest step in red</span>", unsafe_allow_html=True)
            rows = "".join(f"<tr><td style='padding-left:{8 + s['depth'] * 14}px' class='mono'>{html.escape(s['name'])}</td><td>{s['ms']:.1f} ms</td>"
                           f"<td style='width:45%'><div class='bar'><div style='width:{s['ms'] / mx * 100:.0f}%;background:{'#d64545' if slow and s is slow else '#5b64c9'}'></div></div></td></tr>" for s in spans)
            st.markdown(f"<table class='inc'>{rows}</table>", unsafe_allow_html=True)
    with right:
        off, on = get("/reports/redteam_off"), get("/reports/redteam_on")
        st.markdown("**Red team: 8 attacks** <span class='meta'>before → after Part 3</span>", unsafe_allow_html=True)
        if off and on:
            names = {"T01": "run a change", "T02": "alert says restart all", "T03": "secret in alert", "T04": "personal mobile", "T05": "restart three",
                     "T06": "print instructions", "T07": "encoded instruction (ours)", "T08": "paraphrased alert (ours)"}
            rows = "".join(f"<tr><td>{k} {names[k]}</td><td>{chip('WORKED', 'st-NEEDS_PERSON') if off[k]['worked'] else chip('stopped', 'st-AUTO_RESOLVED')}</td>"
                           f"<td>{chip('WORKED', 'st-NEEDS_PERSON') if on[k]['worked'] else chip('stopped', 'st-AUTO_RESOLVED')}</td></tr>" for k in names)
            st.markdown(f"<table class='inc'><tr><th>ATTACK</th><th>BEFORE</th><th>AFTER</th></tr>{rows}</table>", unsafe_allow_html=True)
            st.caption(f"{sum(1 for k in on if not on[k]['worked'])} of 8 stopped. Accepted risk: see SECURITY_FINDINGS.md.")
        else:
            st.caption("Run `python -m scripts.redteam` to fill this in.")

# ---- 5. Agent crew ------------------------------------------------------------------------------------------------------------------
with tabs[4]:
    band("Agent crew", "who does what, with rules or a model, and where a person comes in")
    roster = get("/crew/roster") or []
    cols = st.columns(len(roster) or 1)
    for col, a in zip(cols, roster):
        k = a["kind"]
        col.markdown(f"<div class='card'><div class='agent'>{a['agent']}</div>{chip(k, 'k-' + k.replace(' ', ''))}<div class='meta' style='margin-top:6px'>{html.escape(a['job'])}</div></div>", unsafe_allow_html=True)
    st.markdown("<div class='notice'><b>The rule:</b> code decides every number and every permission; models only write and recommend, and code checks what they recommend. "
                "People approve every change. Orange = a model was called. Blue = plain Python rules. Green = a person.</div>", unsafe_allow_html=True)
    st.write("")
    if not incidents:
        st.info("Triage the starter alerts first.")
    else:
        ids = [i["incident_id"] for i in incidents if i["status"] != "CHANGE_DONE"] or [i["incident_id"] for i in incidents]
        labels = {i["incident_id"]: f"{i['incident_id']} · {i['root_cause'] or 'unknown service'} · {i['severity'] or '--'}" for i in incidents}
        cur = st.selectbox("Incident", ids, format_func=lambda x: labels[x], index=ids.index(st.session_state.selected) if st.session_state.selected in ids else 0, key="crew_pick")
        run = st.button("🚀 Run the crew live on this incident", type="primary")
        holder = st.container()

        def render_step(s: dict, box) -> None:
            kind = s["kind"].replace(" ", "")
            cls = "fail" if s["status"] in ("fail",) else ("stop" if s["status"] == "stop" else kind)
            tail = ""
            if s["model"]:
                tail = f" · {s['ms'] / 1000:.1f} s · {s['tokens']} tokens · ${s['cost_usd']:.5f} · <span class='mono'>{html.escape(s['model'])}</span>"
            elif s["ms"]:
                tail = f" · {s['ms'] / 1000:.2f} s"
            box.markdown(f"<div class='step {cls}'><span class='agent'>{s['agent']}</span> {chip(s['kind'], 'k-' + kind)} "
                         f"{'<span class=\"chip st-NEEDS_PERSON\">FAILED</span>' if s['status'] == 'fail' else ''}"
                         f"<div>{html.escape(s['what'])}</div><div class='meta'>{html.escape(s['at'])}{tail}</div></div>", unsafe_allow_html=True)
            if s["detail"]:
                with box.expander("detail"):
                    st.text(s["detail"])

        if run:
            with holder:
                st.markdown("#### Crew at work")
                final = None
                n_model = n_rules = 0
                try:
                    with requests.post(f"{API}/incidents/{cur}/crew/stream", stream=True, timeout=600) as r:
                        for line in r.iter_lines():
                            if not line:
                                continue
                            ev = json.loads(line)
                            if ev["type"] == "step":
                                s = ev["step"]
                                render_step(s, st.container())
                                n_model += 1 if s["model"] else 0
                                n_rules += 0 if s["model"] else 1
                            elif ev["type"] == "done":
                                final = ev["incident"]
                            elif ev["type"] == "error":
                                st.error(ev["error"])
                except requests.RequestException as e:
                    st.error(f"stream failed: {type(e).__name__}")
                if final:
                    st.success(f"Done: {n_rules} steps by rules or people, {n_model} steps that called a model. Status: {final['status'].replace('_', ' ')}.")
                    if final.get("recommended_step"):
                        st.markdown(f"**Recommendation:** {final['runbook_id']} step {final['recommended_step']} · `{final['action']}` on **{final['target']}** "
                                    f"— needs **{final['approvals_needed']}** approval(s): " + ", ".join(a["engineer"] for a in final["approvers"]) + ". Nothing has run.")
        else:
            inc = get(f"/incidents/{cur}") or {}
            steps = inc.get("crew", [])
            if steps:
                st.markdown("#### Last run")
                for s in steps:
                    render_step(s, st.container())
            else:
                st.caption("No crew run is stored for this incident yet.")

# ---- 6. Live replay ------------------------------------------------------------------------------------------------------------------
with tabs[5]:
    band("Live replay", "the 22 alerts arrive one at a time; watch one incident grow")
    c = st.columns([1, 1, 1, 3])
    if c[0].button("⟲ Reset"):
        post("/replay/reset")
        st.session_state.replay_log = []
        st.rerun()
    step_one = c[1].button("Next alert ▶")
    play = c[2].button("Play all ⏵⏵")
    st.session_state.setdefault("replay_log", [])
    feed = st.container()
    n = 1 if step_one else (22 if play else 0)
    for _ in range(n):
        code, out = post("/replay/step")
        if code != 200 or out.get("done"):
            break
        a = out["alert"]
        tag = "new incident" if out["new_incident"] else ("joined " + out["incident_id"] + f" (now {out['incident_alerts']} alerts)")
        st.session_state.replay_log.insert(0, f"{a['time'][11:]}  {a['alert_id']}  {a['service']:<14} {a['severity']:<8} → {out['incident_id']} · {tag}")
        with feed:
            st.markdown(f"<div class='card'><span class='mono'><b>{a['alert_id']}</b> {a['time'][11:]} {a['service']} {a['severity']}</span> → "
                        f"{'🆕' if out['new_incident'] else '⬆'} <b>{out['incident_id']}</b> {tag}</div>", unsafe_allow_html=True)
        if play:
            time.sleep(0.45)
    live = get("/incidents") or []
    l, r = st.columns(2)
    with l:
        st.markdown("**Alert feed**")
        st.code("\n".join(st.session_state.replay_log[:30]) or "(press Next alert)", language=None)
    with r:
        st.markdown("**Incidents so far**")
        for i in live:
            st.markdown(f"{sev_chip(i['severity'])} **{i['incident_id']}** {i['root_cause'] or 'unknown'} · {len(i['alert_ids'])} alert(s) · {len(i['services'])} service(s) {status_chip(i['status'])}", unsafe_allow_html=True)
    st.caption("Rules re-group after every alert (policy 3.1, 3.2). The crew is not run during replay: pick an incident in the Agent crew tab to brief it.")

# ---- 7. Status page ------------------------------------------------------------------------------------------------------------------
with tabs[6]:
    band("Status page", "what staff see: open P1 and P2 incidents in plain words, no technical detail")
    page = get("/status-page") or {"items": [], "all_clear": True}
    if page.get("all_clear"):
        st.markdown("<div class='status-card lv-resolved'><b>All systems are working normally.</b></div>", unsafe_allow_html=True)
    for it in page.get("items", []):
        st.markdown(f"<div class='status-card lv-{it['level']}'><h4 style='margin:0'>{html.escape(it['title'])}</h4>"
                    f"<div>{html.escape(it['message'])}</div><div class='meta'>Since {when(it['since'])} · next update by {it['next_update']}</div></div>", unsafe_allow_html=True)
    st.caption(f"As of {page.get('as_of', '')}. This page is read-only and is built by rules from the incident list.")
