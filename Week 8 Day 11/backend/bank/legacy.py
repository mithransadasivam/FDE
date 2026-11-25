"""CaseFlow Classic: the bank's 2009 case system (Day 9, done). It has no API: staff work through its screens.

It runs at http://localhost:8100/legacy, on the bank's server. Two ways in:
  - staff sign in with CaseFlow's own password (the course accounts, password kyc-demo), as old systems do
  - the bank's single sign-on: POST /legacy/sso with an access token for the "caseflow" resource. This is how the
    operations agent signs in as the person it works for (token exchange, ENG-802): it never knows a password.

Each person sees the cases in their remit, as in the CRM. Every outcome goes in the case history and the bank's audit log.
"""

import html
import json
import secrets
import time

import jwt
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from bank import core

router = APIRouter(prefix="/legacy")
COOKIE = "cfc_session"
_sessions: dict[str, dict] = {}
OUTCOMES = ["Request more information", "Ready for decision", "Refer to Financial Crime", "Chase applicant"]
REASONS = {"R01": "Missing proof of identity", "R02": "Missing proof of address", "R03": "Documents complete",
           "R04": "Financial crime concern", "R05": "High-risk customer", "R06": "No reply from applicant"}
NEW_STATUS = {"Request more information": "WAITING APPLICANT", "Ready for decision": "READY FOR DECISION",
              "Refer to Financial Crime": "REFERRED TO FINANCIAL CRIME", "Chase applicant": "WAITING APPLICANT"}


# ---------------------------------------------------------------- records
def _seed() -> list[dict]:
    return json.loads((core.DATA / "Day09_Slide10_caseflow_classic.json").read_text(encoding="utf-8"))["cases"]


def cases() -> list[dict]:
    ch = core.load("legacy_changes.json", {})
    out = []
    for c in _seed():
        x = ch.get(c["case_ref"], {})
        out.append({**c, "status": x.get("status", c["status"]), "history": c["history"] + x.get("history", []),
                    "outcomes": x.get("outcomes", [])})
    return out


def _record(ref: str, status: str, entry: dict, outcome: dict) -> None:
    with core._lock:
        ch = core.load("legacy_changes.json", {})
        x = ch.setdefault(ref, {})
        x["status"] = status
        x.setdefault("history", []).append(entry)
        x.setdefault("outcomes", []).append(outcome)
        core.save("legacy_changes.json", ch)


def add_history(ref: str, entry: dict) -> None:
    """A line in a case's history that is not an outcome: a document received, a reply (Day 10)."""
    with core._lock:
        ch = core.load("legacy_changes.json", {})
        ch.setdefault(ref, {}).setdefault("history", []).append(entry)
        core.save("legacy_changes.json", ch)


def _next_reference() -> str:
    n = core.load("legacy_counter.json", {"n": 40016})["n"] + 1
    core.save("legacy_counter.json", {"n": n})
    return f"OUT-{n}"


# ---------------------------------------------------------------- sessions
def _who(request: Request) -> dict | None:
    s = _sessions.get(request.cookies.get(COOKIE, ""))
    if s and time.time() - s["seen"] < 1800:
        s["seen"] = time.time()
        return s
    return None


def _start(person: str, via: str | None) -> RedirectResponse:
    p = core.PEOPLE[person]
    sid = secrets.token_urlsafe(18)
    _sessions[sid] = {"sub": person, "via": via, "role": p["role"], "team": p["team"], "region": p["region"], "name": p["name"],
                      "seen": time.time(), "draft": {}}
    r = RedirectResponse("/legacy/menu", status_code=303)
    r.set_cookie(COOKIE, sid, httponly=True, samesite="lax")
    return r


def _claims(s: dict) -> dict:
    return {"sub": s["sub"], "act": {"sub": s["via"]} if s["via"] else None, "client_id": s["via"] or "caseflow-classic"}


def _visible(s: dict, ref: str) -> dict | None:
    c = next((x for x in cases() if x["case_ref"] == ref.strip().upper()), None)
    return c if c and c["team_id"] in core.teams_for(s) else None


# ---------------------------------------------------------------- the look of 2009
STYLE = """body{font-family:Verdana,Geneva,sans-serif;font-size:12px;background:#d4d0c8;margin:0;color:#000}
.bar{background:linear-gradient(#0a246a,#3a6ea5);color:#fff;padding:6px 10px;font-weight:bold;font-size:13px}
.bar span{float:right;font-weight:normal;font-size:11px}
.page{margin:12px;background:#fff;border:2px inset #808080;padding:12px 16px;min-height:420px}
h1{font-size:16px;margin:0 0 10px;color:#0a246a} h2{font-size:14px;margin:0 0 8px;color:#0a246a} h3{font-size:12px;margin:14px 0 6px}
table.grid{border-collapse:collapse;margin:6px 0 10px} table.grid td,table.grid th{border:1px solid #808080;padding:3px 7px;text-align:left;vertical-align:top}
table.grid th{background:#ece9d8;font-weight:bold} input[type=text],select,textarea{font:12px Verdana;border:2px inset #808080;padding:2px}
input[type=submit],button{font:12px Verdana;background:#ece9d8;border:2px outset #fff;padding:3px 12px;margin-right:6px;cursor:pointer}
label{display:inline-block;width:110px;font-weight:bold;vertical-align:top} .row{margin:6px 0}
p.notice{background:#ffffe1;border:1px solid #808080;padding:6px 8px} p.error{color:#c00000;font-weight:bold}
p.banner{background:#c00000;color:#fff;padding:6px 8px;font-weight:bold} a{color:#0000ee}
.foot{margin:0 12px;font-size:10px;color:#404040}"""


def _page(title: str, body: str, s: dict | None = None) -> HTMLResponse:
    who = f"User: {html.escape(s['sub'])}{' (single sign-on via ' + html.escape(s['via']) + ')' if s and s['via'] else ''}" if s else "Not signed in"
    return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8"><title>CaseFlow Classic · {html.escape(title)}</title>
<style>{STYLE}</style></head><body><div class="bar">CaseFlow Classic 4.2 · Kestrelmoor Bank<span>{who}</span></div>
<div class="page">{body}</div><div class="foot">CaseFlow Classic 4.2 (2009). For bank staff only. Course stand-in: all data is fictional.</div></body></html>""")


def _signin_page(error: str = "") -> HTMLResponse:
    opts = "".join(f'<option value="{u}">{u}</option>' for u in core.PEOPLE)
    return _page("Sign in", f"""<h1>Sign in</h1>{f'<p class="error">{html.escape(error)}</p>' if error else ''}
<form method="post" action="/legacy/signin"><div class="row"><label for="user">User ID</label><select id="user" name="user">{opts}</select></div>
<div class="row"><label for="pw">Password</label><input type="password" id="pw" name="password"></div>
<div class="row"><label></label><input type="submit" value="Sign in"></div></form>
<p class="notice">Course accounts: tom.reyes, grace.mensah, helen.achebe · password {core.PASSWORD}</p>""")


# ---------------------------------------------------------------- sign-in
@router.get("")
@router.get("/")
def home(request: Request):
    return RedirectResponse("/legacy/menu" if _who(request) else "/legacy/signin", status_code=303)


@router.get("/signin")
def signin_page(expired: int = 0):
    return _signin_page("Your session has expired. Please sign in again." if expired else "")


@router.post("/signin")
def signin(user: str = Form(""), password: str = Form("")):
    if user not in core.PEOPLE or not secrets.compare_digest(password, core.PASSWORD):
        return _signin_page("User ID or password not recognised.")
    core.audit("caseflow", {"sub": user, "client_id": "caseflow-classic"}, "sign in", "password", "allowed")
    return _start(user, None)


@router.post("/sso")
def sso(token: str = Form("")):
    """The bank's single sign-on: a token for the caseflow resource, from the bank's sign-in service."""
    try:
        c = core.verify(token, "caseflow")
    except jwt.PyJWTError as e:
        core.audit("caseflow", None, "sign in", "single sign-on", "refused", f"Bad token: {e}")
        return _signin_page(f"Single sign-on failed: {e}")
    if c["sub"] not in core.PEOPLE:
        return _signin_page("Single sign-on failed: no CaseFlow user for this person")
    core.audit("caseflow", c, "sign in", "single sign-on", "allowed")
    act = c.get("act") or {}
    via = act.get("sub")
    if via and (act.get("act") or {}).get("sub"):  # Day 10: a chain, as in the audit ("fde-mcp, for fde-workflow")
        via = f"{via}, for {act['act']['sub']}"
    return _start(c["sub"], via)


@router.get("/signout")
def signout(request: Request):
    _sessions.pop(request.cookies.get(COOKIE, ""), None)
    return RedirectResponse("/legacy/signin", status_code=303)


def _need(request: Request):
    s = _who(request)
    return s, (None if s else RedirectResponse("/legacy/signin?expired=1", status_code=303))


# ---------------------------------------------------------------- screens
@router.get("/menu")
def menu(request: Request):
    s, out = _need(request)
    if out:
        return out
    return _page("Main menu", f"""<h1>Main menu</h1><p>Welcome, {html.escape(s['name'])}.</p>
<ul><li><a href="/legacy/find">Find a case</a></li><li><a href="/legacy/worklist">My work list</a></li><li><a href="/legacy/signout">Sign out</a></li></ul>""", s)


@router.get("/find")
def find(request: Request, ref: str = ""):
    s, out = _need(request)
    if out:
        return out
    err = ""
    if ref:
        c = _visible(s, ref)
        if c:
            return RedirectResponse(f"/legacy/case/{c['case_ref']}", status_code=303)
        err = f'<p class="error">No case found with reference {html.escape(ref)}.</p>'
    return _page("Find a case", f"""<h1>Find a case</h1>{err}<form method="get" action="/legacy/find">
<div class="row"><label for="ref">Case reference</label><input type="text" id="ref" name="ref" value="{html.escape(ref)}" size="14"></div>
<div class="row"><label></label><input type="submit" value="Search"></div></form><p><a href="/legacy/menu">Main menu</a></p>""", s)


@router.get("/worklist")
def worklist(request: Request):
    s, out = _need(request)
    if out:
        return out
    rows = "".join(f'<tr><td><a href="/legacy/case/{c["case_ref"]}">{c["case_ref"]}</a></td><td>{html.escape(c["customer_name"])}</td>'
                   f'<td>{c["team_id"]}</td><td>{c["status"]}</td></tr>' for c in cases() if c["team_id"] in core.teams_for(s))
    return _page("My work list", f"""<h1>My work list</h1><table class="grid"><tr><th>Case</th><th>Customer</th><th>Team</th><th>Status</th></tr>{rows}</table>
<p><a href="/legacy/menu">Main menu</a></p>""", s)


def _not_found(s: dict, ref: str) -> HTMLResponse:
    core.audit("caseflow", _claims(s), "open case", ref, "refused", "Not in this person's remit")
    return _page("Find a case", f'<h1>Find a case</h1><p class="error">No case found with reference {html.escape(ref)}.</p><p><a href="/legacy/menu">Main menu</a></p>', s)


@router.get("/case/{ref}")
def case(ref: str, request: Request):
    s, out = _need(request)
    if out:
        return out
    c = _visible(s, ref)
    if not c:
        return _not_found(s, ref)
    lock = f'<p class="banner">Record locked by {html.escape(c["locked_by"])}.</p>' if c.get("locked_by") else ""
    hist = "".join(f'<tr><td>{h["date"]}</td><td>{html.escape(h["by"])}</td><td>{html.escape(h["entry"])}</td></tr>' for h in c["history"])
    return _page(f"Case {c['case_ref']}", f"""<h1>Case {c['case_ref']}</h1>{lock}
<table class="grid"><tr><th>Customer</th><td>{html.escape(c['customer_name'])} ({c['customer_id']})</td></tr>
<tr><th>Team</th><td>{c['team_id']}</td></tr><tr><th>Received</th><td>{c['received']}</td></tr><tr><th>Status</th><td>{c['status']}</td></tr>
<tr><th>Risk</th><td>{c['risk']}</td></tr><tr><th>Analyst</th><td>{html.escape(c['analyst'])}</td></tr></table>
<h3>Case history</h3><table class="grid"><tr><th>Date</th><th>By</th><th>Entry</th></tr>{hist}</table>
<form method="get" action="/legacy/case/{c['case_ref']}/outcome"><input type="submit" value="Record outcome"></form>
<p><a href="/legacy/menu">Main menu</a></p>""", s)


def _form(s: dict, c: dict, vals: dict, msg: str = "") -> HTMLResponse:
    o = "".join(f'<option{" selected" if vals.get("outcome") == x else ""}>{x}</option>' for x in [""] + OUTCOMES)
    r = "".join(f'<option value="{k}"{" selected" if vals.get("reason") == k else ""}>{k} {v}</option>' for k, v in REASONS.items())
    return _page(f"Record outcome {c['case_ref']}", f"""<h1>Record outcome · {c['case_ref']}</h1>{msg}
<form method="post" action="/legacy/case/{c['case_ref']}/outcome">
<div class="row"><label for="outcome">Outcome</label><select id="outcome" name="outcome">{o}</select></div>
<div class="row"><label for="reason">Reason code</label><select id="reason" name="reason"><option value=""></option>{r}</select></div>
<div class="row"><label for="note">Note</label><textarea id="note" name="note" rows="4" cols="50" maxlength="240">{html.escape(vals.get('note', ''))}</textarea></div>
<div class="row"><label></label><input type="submit" name="do" value="Save"><input type="submit" name="do" value="Cancel"></div></form>""", s)


@router.get("/case/{ref}/outcome")
def outcome_form(ref: str, request: Request):
    s, out = _need(request)
    if out:
        return out
    c = _visible(s, ref)
    return _form(s, c, {}) if c else _not_found(s, ref)


@router.post("/case/{ref}/outcome")
def outcome_save(ref: str, request: Request, do: str = Form("Save"), outcome: str = Form(""), reason: str = Form(""), note: str = Form("")):
    s, out = _need(request)
    if out:
        return out
    c = _visible(s, ref)
    if not c:
        return _not_found(s, ref)
    if do == "Cancel":
        return RedirectResponse(f"/legacy/case/{c['case_ref']}", status_code=303)
    vals = {"outcome": outcome, "reason": reason, "note": note}
    if c.get("locked_by"):
        core.audit("caseflow", _claims(s), "save outcome", c["case_ref"], "refused", f"Record locked by {c['locked_by']}")
        return _form(s, c, vals, f'<p class="banner">Record locked by {html.escape(c["locked_by"])}. Your changes were not saved.</p>')
    errs = [m for bad, m in [(outcome not in OUTCOMES, "Choose an outcome."), (reason not in REASONS, "Choose a reason code."),
                             (not note.strip(), "Write a note."), (len(note) > 240, "The note is longer than 240 characters.")] if bad]
    if errs:
        return _form(s, c, vals, "".join(f'<p class="error">{e}</p>' for e in errs))
    s["draft"][c["case_ref"]] = vals
    return RedirectResponse(f"/legacy/case/{c['case_ref']}/confirm", status_code=303)


@router.get("/case/{ref}/confirm")
def confirm_page(ref: str, request: Request):
    s, out = _need(request)
    if out:
        return out
    c = _visible(s, ref)
    if not c:
        return _not_found(s, ref)
    d = s["draft"].get(c["case_ref"])
    if not d:
        return RedirectResponse(f"/legacy/case/{c['case_ref']}/outcome", status_code=303)
    offer = (f'<p class="notice">The applicant asked on {c["withdraw_offered"]} whether they can withdraw. You may withdraw the application instead.</p>'
             if c.get("withdraw_offered") else "")
    wd = '<input type="submit" name="do" value="Withdraw case">' if c.get("withdraw_offered") else ""
    return _page(f"Confirm {c['case_ref']}", f"""<h1>Confirm outcome · {c['case_ref']}</h1>{offer}
<table class="grid"><tr><th>Outcome</th><td>{html.escape(d['outcome'])}</td></tr><tr><th>Reason code</th><td>{d['reason']} {REASONS[d['reason']]}</td></tr>
<tr><th>Note</th><td>{html.escape(d['note'])}</td></tr></table>
<form method="post" action="/legacy/case/{c['case_ref']}/confirm"><input type="submit" name="do" value="Back">{wd}<input type="submit" name="do" value="Confirm"></form>""", s)


@router.post("/case/{ref}/confirm")
def confirm(ref: str, request: Request, do: str = Form("")):
    s, out = _need(request)
    if out:
        return out
    c = _visible(s, ref)
    if not c:
        return _not_found(s, ref)
    d = s["draft"].get(c["case_ref"])
    if do == "Back" or not d:
        return RedirectResponse(f"/legacy/case/{c['case_ref']}/outcome", status_code=303)
    by = s["sub"] + (f" via {s['via']}" if s["via"] else "")
    today = time.strftime("%d/%m/%Y")
    ref_no = _next_reference()
    if do == "Withdraw case" and c.get("withdraw_offered"):
        _record(c["case_ref"], "WITHDRAWN", {"date": today, "by": by, "entry": f"Case withdrawn. Reference {ref_no}."},
                {"reference": ref_no, "outcome": "Case withdrawn", "by": s["sub"], "via": s["via"], "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
        core.audit("caseflow", _claims(s), "withdraw case", c["case_ref"], "allowed", ref_no)
        s["draft"].pop(c["case_ref"], None)
        return _page("Case withdrawn", f"""<h1>Case withdrawn</h1><p class="notice">Reference {ref_no}</p>
<p><a href="/legacy/case/{c['case_ref']}">Back to case</a></p>""", s)
    if do != "Confirm":
        return RedirectResponse(f"/legacy/case/{c['case_ref']}/confirm", status_code=303)
    _record(c["case_ref"], NEW_STATUS[d["outcome"]],
            {"date": today, "by": by, "entry": f"Outcome: {d['outcome']} ({d['reason']}). {d['note']} Reference {ref_no}."},
            {"reference": ref_no, "outcome": d["outcome"], "reason": d["reason"], "note": d["note"], "by": s["sub"], "via": s["via"],
             "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    core.audit("caseflow", _claims(s), "record outcome", c["case_ref"], "allowed", f"{d['outcome']} · {ref_no}")
    s["draft"].pop(c["case_ref"], None)
    return _page("Outcome recorded", f"""<h1>Outcome recorded</h1><p class="notice">{html.escape(d['outcome'])} · Reference {ref_no}</p>
<p><a href="/legacy/case/{c['case_ref']}">Back to case</a></p>""", s)


# ---------------------------------------------------------------- course helper (not part of CaseFlow: it has no API)
course = APIRouter()


@course.get("/course/caseflow-log")
def caseflow_log(limit: int = 50):
    """What CaseFlow Classic recorded, for the console's Agent runs screen and the tests."""
    rows = [{"case_ref": c["case_ref"], **o} for c in cases() for o in c["outcomes"]]
    rows.sort(key=lambda r: r["at"], reverse=True)
    return {"outcomes": rows[:limit], "cases": {c["case_ref"]: c["status"] for c in cases()}}

