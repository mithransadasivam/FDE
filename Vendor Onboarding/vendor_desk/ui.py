"""Mission-control visuals for the app: pure functions that turn case data into HTML / inline SVG strings.

Nothing here talks to a model or a database. Every value that came from an email, a document or a vendor name is passed
through esc() before it is placed in markup, so a vendor called "<script>" is shown as text, never run (tests/test_ui.py).
"""
import html
import math
import re

from vendor_desk import safety

CYAN, VIOLET, PINK, GREEN, AMBER, RED, BLUE, GREY = "#38e8ff", "#9b6bff", "#ff5fa2", "#3dffb0", "#ffc857", "#ff5c70", "#5b8cff", "#7d82a8"

STATE_COLOR = {"RECEIVED": CYAN, "CHECKING": CYAN, "WAITING_FOR_VENDOR": AMBER, "READY_FOR_APPROVAL": BLUE,
               "APPROVED": GREEN, "CREATED": GREEN, "REJECTED": GREY, "STOPPED": RED}
CHECK_ORDER = ["documents", "duplicate", "watchlist", "payment_terms", "bank", "spend"]
CHECK_LABEL = {"documents": "Documents", "duplicate": "Duplicate", "watchlist": "Watch list", "payment_terms": "Terms",
               "bank": "Bank", "spend": "Spend"}
RESULT_GLYPH = {"pass": ("✔", GREEN), "review": ("⚠", AMBER), "fail": ("✖", RED), "missing": ("?", "#ff9a4d")}
FLAG_WEIGHT = {"duplicate_vendor": 95, "watchlist_hit": 95, "possible_injection": 85, "bank_account_shared": 80,
               "watchlist_near_match": 75, "bank_holder_mismatch": 75, "possible_duplicate": 70, "bank_country_mismatch": 65,
               "insurance_expired": 35, "payment_terms_over_limit": 30}
SPECIALISTS = ("intake", "documents", "compliance", "finance", "followup")

LIVE_RUNS = [  # the three live-model runs of the single agent (see EVAL_REPORT.md)
    ("RUN 1", "19/19 right", "11 review problems", GREEN),
    ("RUN 2", "18/19 right", "fooled by the 'skip the checks' email", RED),
    ("RUN 3", "cut short", "API key limit reached", AMBER),
    ("RUN 4", "19/19 right", "DeepSeek V4 Flash: single agent and team both clean", GREEN),
]


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def risk_score(case: dict) -> int:
    scores = [FLAG_WEIGHT[f] for f in case.get("flags", []) if f in FLAG_WEIGHT]
    if case.get("missing_items"):
        scores.append(30)
    if not scores:
        return 6 if case.get("checks") else 0
    return min(100, max(scores) + 4 * (len(scores) - 1))


def risk_color(score: int) -> str:
    return GREEN if score < 25 else AMBER if score < 50 else "#ff9a4d" if score < 75 else RED


# ---------------------------------------------------------------------------------------------- global theme
CSS = f"""
<style>
.stApp {{ background:
  radial-gradient(1200px 600px at 10% -10%, rgba(155,107,255,.20), transparent 60%),
  radial-gradient(900px 500px at 95% 0%, rgba(56,232,255,.14), transparent 55%),
  radial-gradient(900px 700px at 50% 120%, rgba(255,95,162,.10), transparent 60%), #080a17; }}
.stApp::before {{ content:""; position:fixed; inset:0; pointer-events:none; opacity:.35;
  background-image: linear-gradient(rgba(255,255,255,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.035) 1px, transparent 1px);
  background-size: 46px 46px; mask-image: radial-gradient(ellipse at 50% 20%, #000 20%, transparent 75%); }}
.block-container {{ padding-top: 3.2rem; max-width: 1500px; }}
[data-testid="stSidebar"] {{ background: linear-gradient(180deg, #0d1030, #080a17); border-right:1px solid rgba(255,255,255,.07); }}
h1,h2,h3,h4 {{ letter-spacing:.01em; }}
.glass {{ background: rgba(255,255,255,.045); border:1px solid rgba(255,255,255,.10); border-radius:16px; padding:16px 18px;
  backdrop-filter: blur(8px); box-shadow: 0 8px 30px rgba(0,0,0,.35); }}
.mono {{ font-family: ui-monospace, "Cascadia Code", Consolas, monospace; }}
.tiny {{ font-size:.72rem; color:{GREY}; letter-spacing:.08em; text-transform:uppercase; }}
.muted {{ color:#a9aed4; }}

/* hero */
.hero {{ position:relative; overflow:hidden; border-radius:20px; padding:26px 30px; margin-bottom:14px;
  background: linear-gradient(120deg, rgba(155,107,255,.30), rgba(56,232,255,.16) 55%, rgba(255,95,162,.22));
  border:1px solid rgba(255,255,255,.14); box-shadow:0 20px 60px rgba(60,30,160,.35); }}
.hero::after {{ content:""; position:absolute; top:0; bottom:0; width:120px; left:-160px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,.18), transparent); transform: skewX(-20deg);
  animation: sweep 6s ease-in-out infinite; }}
@keyframes sweep {{ 0%,55% {{ left:-160px; }} 100% {{ left:110%; }} }}
.hero h1 {{ margin:0; font-size:2.1rem; font-weight:800; letter-spacing:.04em;
  background: linear-gradient(90deg, #fff, {CYAN} 45%, {PINK}); -webkit-background-clip:text; background-clip:text; color:transparent; }}
.hero .tag {{ color:#d8dcff; margin-top:4px; letter-spacing:.14em; font-size:.78rem; text-transform:uppercase; }}
.stats {{ display:flex; gap:12px; margin-top:18px; flex-wrap:wrap; }}
.stat {{ flex:1; min-width:150px; background:rgba(8,10,23,.55); border:1px solid rgba(255,255,255,.12); border-radius:14px; padding:10px 14px; }}
.stat b {{ display:block; font-size:1.9rem; line-height:1.1; text-shadow:0 0 18px currentColor; }}
.stat span {{ font-size:.7rem; letter-spacing:.1em; text-transform:uppercase; color:#b8bde6; }}

/* ticker */
.ticker {{ overflow:hidden; white-space:nowrap; border:1px solid rgba(255,255,255,.09); border-radius:12px; background:rgba(0,0,0,.28); margin-bottom:14px; }}
.ticker .belt {{ display:inline-block; padding:8px 0; animation: belt 70s linear infinite; }}
.ticker:hover .belt {{ animation-play-state: paused; }}
@keyframes belt {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-50%); }} }}
.tick {{ display:inline-block; margin:0 22px; font-size:.78rem; color:#c9cdf2; }}
.tick b {{ color:{CYAN}; }} .tick i {{ color:{GREY}; font-style:normal; }}

/* kanban */
.col-head {{ display:flex; align-items:center; justify-content:space-between; font-size:.72rem; letter-spacing:.12em; text-transform:uppercase;
  padding:8px 12px; border-radius:10px; margin-bottom:8px; font-weight:700; border:1px solid rgba(255,255,255,.1); }}
.kcard {{ position:relative; border-radius:14px; padding:12px 12px 10px 12px; margin-bottom:4px; background:rgba(255,255,255,.05);
  border:1px solid rgba(255,255,255,.10); transition: transform .2s, box-shadow .2s; }}
.kcard:hover {{ transform: translateY(-3px); box-shadow:0 10px 30px rgba(0,0,0,.45); }}
.kcard.human {{ animation: glow 2.6s ease-in-out infinite; }}
@keyframes glow {{ 0%,100% {{ box-shadow:0 0 0 rgba(255,92,112,0); }} 50% {{ box-shadow:0 0 22px rgba(255,92,112,.35); }} }}
.kcard .id {{ font-size:.7rem; color:{GREY}; letter-spacing:.1em; }}
.kcard .name {{ font-weight:700; font-size:.92rem; margin:2px 0 6px; padding-right:46px; }}
.kcard .next {{ font-size:.72rem; color:#a9aed4; margin-top:6px; line-height:1.35; }}
.ring {{ position:absolute; top:10px; right:10px; width:40px; height:40px; border-radius:50%; display:grid; place-items:center;
  font-size:.7rem; font-weight:800; }}
.ring span {{ background:#0b0d1e; width:30px; height:30px; border-radius:50%; display:grid; place-items:center; }}
.chip {{ display:inline-block; padding:1px 8px; margin:1px 4px 1px 0; border-radius:999px; font-size:.64rem; letter-spacing:.03em;
  background:rgba(255,200,87,.13); color:{AMBER}; border:1px solid rgba(255,200,87,.35); }}
.chip.red {{ background:rgba(255,92,112,.13); color:{RED}; border-color:rgba(255,92,112,.4); }}
.pillx {{ display:inline-block; padding:3px 12px; border-radius:999px; font-size:.72rem; font-weight:800; letter-spacing:.08em; }}

/* pipeline */
.pipe {{ border-radius:16px; padding:6px 10px 0; background: rgba(255,255,255,.035); border:1px solid rgba(255,255,255,.09); }}
.pipe text {{ font-family: Segoe UI, system-ui, sans-serif; }}
.pulse {{ animation: pulse 1.8s ease-in-out infinite; transform-box: fill-box; transform-origin:center; }}
@keyframes pulse {{ 0%,100% {{ transform: scale(1); opacity:.9; }} 50% {{ transform: scale(1.18); opacity:.35; }} }}
.flow {{ stroke-dasharray: 6 8; animation: flow 1.1s linear infinite; }}
@keyframes flow {{ to {{ stroke-dashoffset: -28; }} }}

/* evidence */
.egrid {{ display:grid; grid-template-columns: repeat(auto-fill,minmax(250px,1fr)); gap:10px; }}
.ecard {{ border-radius:14px; padding:12px 14px; background:rgba(255,255,255,.05); border:1px solid rgba(255,255,255,.1); position:relative; overflow:hidden; }}
.ecard::before {{ content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--c); box-shadow:0 0 14px var(--c); }}
.ecard h5 {{ margin:0 0 4px; font-size:.78rem; letter-spacing:.1em; text-transform:uppercase; color:#cfd3ff; display:flex; justify-content:space-between; }}
.ecard .glyph {{ color:var(--c); font-weight:900; text-shadow:0 0 12px var(--c); }}
.ecard p {{ margin:0; font-size:.78rem; color:#b8bde6; line-height:1.45; }}
.sec {{ display:inline-block; margin-top:6px; padding:0 8px; border-radius:6px; background:rgba(155,107,255,.18); color:#c9b3ff; font-size:.68rem; }}

/* vault */
.vault {{ border-radius:18px; padding:16px; background: linear-gradient(160deg, rgba(255,200,87,.10), rgba(155,107,255,.10)); border:1px solid rgba(255,200,87,.30); text-align:center; }}
.keys {{ display:flex; justify-content:center; gap:16px; margin:12px 0; }}
.slot {{ width:92px; height:104px; border-radius:16px; border:2px dashed rgba(255,255,255,.22); display:flex; flex-direction:column; align-items:center; justify-content:center; font-size:.66rem; color:{GREY}; }}
.slot.on {{ border:2px solid {AMBER}; background:rgba(255,200,87,.12); color:#ffe9b8; box-shadow:0 0 24px rgba(255,200,87,.45); animation: turn .8s ease-out; }}
@keyframes turn {{ from {{ transform: rotate(-40deg) scale(.7); opacity:0; }} to {{ transform:none; opacity:1; }} }}
.slot .k {{ font-size:2rem; }}
.door {{ font-size:2.6rem; margin-top:4px; }}
.door.open {{ animation: pop .7s ease-out; filter: drop-shadow(0 0 14px {GREEN}); }}
@keyframes pop {{ from {{ transform: scale(.4) rotate(-25deg); }} to {{ transform:none; }} }}

/* stamp */
.stamp {{ display:inline-block; transform: rotate(-7deg); border:3px solid var(--c); color:var(--c); padding:4px 16px; border-radius:10px;
  font-weight:900; letter-spacing:.14em; text-transform:uppercase; font-size:.95rem; opacity:.92; box-shadow: inset 0 0 12px var(--c); animation: slam .5s ease-out; }}
@keyframes slam {{ from {{ transform: rotate(-7deg) scale(2.4); opacity:0; }} to {{ transform: rotate(-7deg) scale(1); opacity:.92; }} }}

/* shield */
.shield {{ position:relative; border-radius:16px; padding:14px 18px 14px 74px; background: linear-gradient(100deg, rgba(255,92,112,.20), rgba(255,92,112,.05));
  border:1px solid rgba(255,92,112,.5); margin:10px 0; }}
.shield .ico {{ position:absolute; left:18px; top:12px; font-size:2.2rem; }}
.shield .ico::after {{ content:""; position:absolute; inset:-8px; border-radius:50%; border:2px solid {RED}; animation: ping 1.8s ease-out infinite; }}
@keyframes ping {{ from {{ transform:scale(.6); opacity:.9; }} to {{ transform:scale(1.7); opacity:0; }} }}

/* letter */
.letter {{ background:#f6f1e4; color:#2b2a33; border-radius:6px; padding:18px 20px; font-family: Georgia, serif; font-size:.82rem; line-height:1.55;
  box-shadow: 0 14px 30px rgba(0,0,0,.45); transform: rotate(-.6deg); position:relative; white-space:pre-wrap; }}
.letter::after {{ content:"DRAFT · NOT SENT"; position:absolute; top:10px; right:14px; border:2px solid #c0392b; color:#c0392b; padding:1px 8px; border-radius:4px; font:700 .62rem sans-serif; letter-spacing:.12em; transform: rotate(4deg); }}

/* timeline */
.tl {{ position:relative; margin-left:14px; padding-left:26px; border-left:2px solid rgba(255,255,255,.12); }}
.ev {{ position:relative; margin:0 0 10px; padding:9px 14px; border-radius:12px; background:rgba(255,255,255,.045); border:1px solid rgba(255,255,255,.09);
  opacity:0; animation: rise .45s ease-out forwards; animation-delay: calc(var(--i) * 45ms); }}
@keyframes rise {{ from {{ opacity:0; transform: translateX(-14px); }} to {{ opacity:1; transform:none; }} }}
@keyframes rise2 {{ from {{ opacity:0; transform: translateX(-14px); }} to {{ opacity:1; transform:none; }} }}
.ev::before {{ content:""; position:absolute; left:-37px; top:14px; width:14px; height:14px; border-radius:50%; background:var(--c); box-shadow:0 0 14px var(--c); border:2px solid #080a17; }}
.ev .who {{ font-weight:700; font-size:.82rem; color:var(--c); }}
.ev .det {{ font-size:.82rem; color:#dfe2ff; margin-top:2px; }}
.ev .evi {{ font-size:.72rem; color:{GREY}; margin-top:2px; }}
.hash {{ display:inline-block; margin:6px 6px 0 0; padding:0 8px; border-radius:6px; background:rgba(56,232,255,.10); color:{CYAN}; font-size:.64rem; border:1px solid rgba(56,232,255,.25); }}

/* arena */
.duel {{ display:grid; grid-template-columns: 1fr 70px 1fr; gap:10px; align-items:stretch; }}
.fighter {{ border-radius:18px; padding:18px; text-align:center; border:1px solid rgba(255,255,255,.12); }}
.fighter h3 {{ margin:0; letter-spacing:.16em; font-size:.85rem; }}
.fighter .big {{ font-size:2.6rem; font-weight:900; line-height:1.1; text-shadow:0 0 22px currentColor; margin:6px 0; }}
.vs {{ align-self:center; text-align:center; font-weight:900; font-size:1.5rem; color:{PINK}; text-shadow:0 0 16px {PINK}; }}
.bars .row {{ display:grid; grid-template-columns: 170px 1fr 1fr; gap:10px; align-items:center; margin:8px 0; font-size:.8rem; }}
.bar {{ height:20px; border-radius:6px; background:rgba(255,255,255,.07); position:relative; overflow:hidden; }}
.bar i {{ position:absolute; inset:0 auto 0 0; border-radius:6px; animation: grow 1.1s ease-out; }}
.bar em {{ position:absolute; right:8px; top:1px; font-size:.7rem; font-style:normal; }}
@keyframes grow {{ from {{ width:0 !important; }} }}
.heat {{ display:flex; gap:4px; flex-wrap:wrap; margin:6px 0 12px; }}
.cell {{ width:34px; height:34px; border-radius:8px; display:grid; place-items:center; font-size:.6rem; font-weight:800; color:#06101a; }}
.runs {{ display:flex; gap:10px; flex-wrap:wrap; }}
.runchip {{ flex:1; min-width:190px; border-radius:14px; padding:10px 14px; border:1px solid rgba(255,255,255,.12); background:rgba(255,255,255,.04); }}

/* redteam */
mark {{ background: rgba(255,92,112,.35); color:#fff; padding:0 3px; border-radius:4px; box-shadow:0 0 10px rgba(255,92,112,.5); }}
.verdict {{ border-radius:14px; padding:14px 18px; margin-top:10px; }}
.stButton > button {{ border-radius:12px; border:1px solid rgba(255,255,255,.18); }}
.stButton > button[kind="primary"] {{ background: linear-gradient(90deg, {VIOLET}, {CYAN}); color:#06101a; font-weight:800; border:none; }}
</style>
"""


# ---------------------------------------------------------------------------------------------- hero and ticker
def hero(cases: list[dict]) -> str:
    waiting = sum(1 for c in cases if c["status"] in ("READY_FOR_APPROVAL", "STOPPED"))
    created = sum(1 for c in cases if c["status"] == "CREATED")
    shields = sum(1 for c in cases if c.get("injection"))
    sendbacks = sum((c.get("reviewer") or {}).get("revisions", 0) for c in cases)
    calls = int(sum(c["usage"]["model_calls"] for c in cases))
    tiles = [("CASES ON THE BOARD", len(cases), CYAN), ("WAITING FOR A HUMAN", waiting, AMBER), ("VENDORS CREATED", created, GREEN),
             ("INJECTIONS BLOCKED", shields, RED), ("REVIEWER SEND-BACKS", sendbacks, VIOLET), ("MODEL CALLS SPENT", calls, PINK)]
    stats = "".join(f'<div class="stat" style="color:{col}"><b>{n}</b><span>{esc(label)}</span></div>' for label, n, col in tiles)
    return ('<div class="hero"><h1>VENDOR ONBOARDING · MISSION CONTROL</h1>'
            '<div class="tag">Agents check &nbsp;·&nbsp; a person decides &nbsp;·&nbsp; every step on the record</div>'
            f'<div class="stats">{stats}</div></div>')


def ticker(events: list[dict]) -> str:
    if not events:
        return ""
    items = "".join(f'<span class="tick"><b>{esc(e["case_id"])}</b> <i>{esc(e["at"][11:19])}</i> {esc(e["who"])}: {esc(e["detail"][:90])}</span>'
                    for e in events)
    return f'<div class="ticker"><div class="belt">{items}{items}</div></div>'


# ---------------------------------------------------------------------------------------------- board
def column_header(title: str, color: str, n: int) -> str:
    return (f'<div class="col-head" style="color:{color};background:linear-gradient(90deg,{color}22,transparent)">'
            f'<span>{esc(title)}</span><span>{n}</span></div>')


def kanban_card(case: dict) -> str:
    score = risk_score(case)
    col = risk_color(score)
    needs_human = case["status"] in ("STOPPED", "READY_FOR_APPROVAL")
    flags = "".join(f'<span class="chip {"red" if FLAG_WEIGHT.get(f, 0) >= 65 else ""}">{esc(f.replace("_", " "))}</span>'
                    for f in case["flags"][:3])
    keys = ""
    if case.get("approvers_required"):
        n, need = len(case["approvals"]), case["approvers_required"]
        keys = f'<div class="next">{"🔑" * n}{"▫️" * (need - n)} &nbsp;{n}/{need} keys</div>'
    return (f'<div class="kcard {"human" if needs_human else ""}" style="border-left:3px solid {STATE_COLOR.get(case["status"], GREY)}">'
            f'<div class="ring" style="background:conic-gradient({col} {score * 3.6}deg, rgba(255,255,255,.10) 0)"><span style="color:{col}">{score}</span></div>'
            f'<div class="id mono">{esc(case["case_id"])}</div><div class="name">{esc(case["vendor_name"] or case["subject"])}</div>'
            f'{flags}{keys}<div class="next">{esc(case["next_step"][:110])}</div></div>')


BOARD_COLUMNS = [("INCOMING", ("RECEIVED", "CHECKING"), CYAN), ("WAITING FOR VENDOR", ("WAITING_FOR_VENDOR",), AMBER),
                 ("NEEDS A HUMAN", ("STOPPED",), RED), ("READY TO APPROVE", ("READY_FOR_APPROVAL",), BLUE),
                 ("VENDOR CREATED", ("APPROVED", "CREATED"), GREEN), ("REJECTED", ("REJECTED",), GREY)]


# ---------------------------------------------------------------------------------------------- case file
def station_states(case: dict) -> dict:
    done = set(case["per_role"])
    st = {r: ("done" if r in done else "idle") for r in ("intake", "documents", "finance", "compliance")}
    stop = case.get("stop_reason") or ""
    for r in st:
        if stop.startswith(r) and case["status"] == "STOPPED" and not case.get("decision"):
            st[r] = "fail"
    rv = case.get("reviewer")
    st["reviewer"] = "done" if rv and rv["verdict"] == "approve" else ("fail" if stop.startswith("Revision") else "idle")
    status = case["status"]
    if status in ("READY_FOR_APPROVAL",) or (status == "STOPPED" and case.get("decision")):
        st["gate"] = "wait"
    elif status in ("APPROVED", "CREATED", "REJECTED"):
        st["gate"] = "done"
    elif status == "WAITING_FOR_VENDOR":
        st["gate"] = "pause"
    elif status == "STOPPED":
        st["gate"] = "fail"
    else:
        st["gate"] = "idle"
    st["vault"] = "done" if status == "CREATED" else ("fail" if status == "REJECTED" else "idle")
    return st


NODE_STYLE = {"done": (GREEN, "rgba(61,255,176,.16)"), "wait": (VIOLET, "rgba(155,107,255,.25)"), "pause": (AMBER, "rgba(255,200,87,.18)"),
              "fail": (RED, "rgba(255,92,112,.20)"), "idle": ("#4b5078", "rgba(255,255,255,.04)"), "active": (CYAN, "rgba(56,232,255,.22)")}


def pipeline_svg(case: dict, active: tuple = ()) -> str:
    st = station_states(case)
    for k in active:
        if k in st:
            st[k] = "active"
    nodes = [("intake", "📨", "INTAKE"), ("documents", "📄", "DOCUMENTS"), ("finance", "💷", "FINANCE"), ("compliance", "🕵️", "COMPLIANCE"),
             ("reviewer", "⚖️", "REVIEWER"), ("gate", "🧑", "YOU"), ("vault", "🏦", "VENDOR MASTER")]
    xs = [90 + i * 153 for i in range(len(nodes))]
    parts = ['<svg viewBox="0 0 1100 150" width="100%" xmlns="http://www.w3.org/2000/svg">']
    for i in range(len(nodes) - 1):
        a, b = nodes[i][0], nodes[i + 1][0]
        active = st[a] == "done" and st[b] in ("wait", "idle", "pause", "done", "active")
        col = GREEN if st[a] == "done" and st[b] != "idle" else "#3a3f66"
        if st[a] == "done" and st[b] in ("wait", "pause"):
            col = VIOLET if st[b] == "wait" else AMBER
        cls = "flow" if (st[a] == "done" and st[b] in ("wait", "pause", "active")) or st[b] == "active" else ""
        parts.append(f'<line x1="{xs[i] + 30}" y1="62" x2="{xs[i + 1] - 30}" y2="62" stroke="{col}" stroke-width="3" class="{cls}" stroke-linecap="round"/>')
        _ = active
    for (key, icon, label), x in zip(nodes, xs):
        col, fill = NODE_STYLE[st[key]]
        pulse = f'<circle cx="{x}" cy="62" r="30" fill="none" stroke="{col}" stroke-width="2" class="pulse"/>' if st[key] in ("wait", "pause", "active") else ""
        sub = {"done": "done", "wait": "needs you", "pause": "waiting", "fail": "stopped", "idle": "", "active": "working…"}[st[key]]
        parts.append(f'{pulse}<circle cx="{x}" cy="62" r="30" fill="{fill}" stroke="{col}" stroke-width="2.5"/>'
                     f'<text x="{x}" y="71" text-anchor="middle" font-size="26">{icon}</text>'
                     f'<text x="{x}" y="118" text-anchor="middle" font-size="11" font-weight="700" letter-spacing="1.5" fill="#cfd3ff">{esc(label)}</text>'
                     f'<text x="{x}" y="134" text-anchor="middle" font-size="10" fill="{col}">{sub}</text>')
    sb = (case.get("reviewer") or {}).get("revisions", 0)
    if sb:
        x = (xs[3] + xs[4]) // 2
        parts.append(f'<path d="M {xs[4] - 6} 30 Q {x} -6 {xs[3] + 6} 30" fill="none" stroke="{PINK}" stroke-width="2" stroke-dasharray="4 4" class="flow"/>'
                     f'<text x="{x}" y="14" text-anchor="middle" font-size="10" fill="{PINK}">sent back ×{sb}</text>')
    parts.append("</svg>")
    return '<div class="pipe">' + "".join(parts) + "</div>"


def radar_svg(case: dict) -> str:
    cx, cy, r = 150, 140, 100
    values = {"pass": 0.92, "review": 0.45, "missing": 0.3, "fail": 0.12}
    by = {c["check"]: c["result"] for c in case.get("checks", [])}
    n = len(CHECK_ORDER)

    def pt(i, k):
        ang = -math.pi / 2 + 2 * math.pi * i / n
        return cx + r * k * math.cos(ang), cy + r * k * math.sin(ang)

    rings = "".join('<polygon points="' + " ".join("%.1f,%.1f" % pt(i, k) for i in range(n)) + '" fill="none" stroke="rgba(255,255,255,.12)"/>'
                    for k in (0.33, 0.66, 1.0))
    spokes = "".join('<line x1="%d" y1="%d" x2="%.1f" y2="%.1f" stroke="rgba(255,255,255,.10)"/>' % ((cx, cy) + pt(i, 1)) for i in range(n))
    poly = " ".join("%.1f,%.1f" % pt(i, values.get(by.get(c), 0.5)) for i, c in enumerate(CHECK_ORDER))
    worst = min((values.get(by.get(c), 0.5) for c in CHECK_ORDER), default=1)
    col = GREEN if worst > 0.8 else AMBER if worst > 0.4 else RED
    dots, labels = "", ""
    for i, c in enumerate(CHECK_ORDER):
        x, y = pt(i, values.get(by.get(c), 0.5))
        gcol = RESULT_GLYPH.get(by.get(c), ("·", GREY))[1]
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{gcol}"/>'
        lx, ly = pt(i, 1.25)
        labels += f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="10" fill="#cfd3ff">{esc(CHECK_LABEL[c])}</text>'
    return (f'<svg viewBox="0 0 300 280" width="100%">{rings}{spokes}'
            f'<polygon points="{poly}" fill="{col}" fill-opacity=".22" stroke="{col}" stroke-width="2.5"><animate attributeName="fill-opacity" values=".12;.3;.12" dur="3s" repeatCount="indefinite"/></polygon>'
            f'{dots}{labels}</svg>')


def evidence_cards(case: dict) -> str:
    out = []
    for c in sorted(case.get("checks", []), key=lambda c: CHECK_ORDER.index(c["check"])):
        glyph, col = RESULT_GLYPH[c["result"]]
        out.append(f'<div class="ecard" style="--c:{col}"><h5><span>{esc(CHECK_LABEL[c["check"]])}</span><span class="glyph">{glyph} {esc(c["result"].upper())}</span></h5>'
                   f'<p>{esc(c["evidence"])}</p><span class="sec">policy {esc(c["policy_section"])}</span> '
                   f'<span class="sec" style="background:rgba(56,232,255,.12);color:{CYAN}">{esc(c["tool"])}</span></div>')
    return '<div class="egrid">' + "".join(out) + "</div>"


def vault(case: dict) -> str:
    need = case.get("approvers_required") or 1
    approvals = case.get("approvals", [])
    slots = ""
    for i in range(need):
        if i < len(approvals):
            a = approvals[i]
            initials = esc("".join(w[0] for w in re.split(r"[.@_\- ]+", a["approver"])[:2]).upper())
            slots += f'<div class="slot on"><div class="k">🔑</div><b>{initials}</b><span>{esc(a["approver"][:18])}</span></div>'
        else:
            slots += f'<div class="slot"><div class="k" style="opacity:.25">🗝️</div>key {i + 1}<span>awaiting</span></div>'
    status = case["status"]
    if status == "CREATED":
        door = f'<div class="door open">🔓</div><div style="color:{GREEN};font-weight:800">VAULT OPEN · {esc(case.get("vendor_id"))} created</div>'
    elif status == "REJECTED":
        door = f'<div class="door">⛔</div><div style="color:{GREY}">closed by a person</div>'
    else:
        door = f'<div class="door">🔒</div><div class="tiny">the only write happens here, once, after every key is turned</div>'
    title = "TWO-KEY RULE · over £25,000" if need == 2 else "ONE-KEY RULE · up to £25,000"
    return f'<div class="vault"><div class="tiny" style="color:{AMBER}">{title}</div><div class="keys">{slots}</div>{door}</div>'


def stamp(case: dict) -> str:
    rv = case.get("reviewer")
    if not rv:
        return ""
    if rv["verdict"] != "approve":
        return f'<span class="stamp" style="--c:{RED}">sent back</span>'
    if rv.get("revisions"):
        return f'<span class="stamp" style="--c:{AMBER}">fixed after {rv["revisions"]} send-back</span>'
    return f'<span class="stamp" style="--c:{GREEN}">verified</span>'


def shield(case: dict) -> str:
    if not case.get("injection"):
        return ""
    d = case.get("injection_detail") or {}
    pats = "".join(f'<span class="chip red">{esc(p.replace("_", " "))}</span>' for p in d.get("patterns", []))
    where = ", ".join(esc(w) for w in d.get("found_in", [])) or "the request"
    return (f'<div class="shield"><div class="ico">🛡️</div><b style="color:{RED};letter-spacing:.08em">INJECTION SHIELD TRIGGERED</b>'
            f'<div style="font-size:.82rem;margin-top:4px">Text in <b>{where}</b> tried to give the system orders. It was treated as <b>data</b>: '
            'every check still ran, the decision was forced to <b>stop for a person</b>, and nothing can be approved without one (§1.2, §7.2).</div>'
            f'<div style="margin-top:6px">{pats}</div></div>')


def letter(draft: dict | None) -> str:
    if not draft:
        return ""
    return (f'<div class="tiny" style="margin-bottom:4px">To: {esc(draft["to"])}<br>Subject: {esc(draft["subject"])}</div>'
            f'<div class="letter">{esc(draft["body"])}</div>')


def usage_bars(per_role: dict) -> str:
    if not per_role:
        return ""
    top = max((v["model_calls"] for v in per_role.values()), default=1) or 1
    palette = {"intake": CYAN, "documents": BLUE, "compliance": VIOLET, "finance": GREEN, "followup": AMBER, "supervisor": PINK}
    rows = ""
    for role, v in per_role.items():
        w = max(4, int(100 * v["model_calls"] / top))
        rows += (f'<div style="display:grid;grid-template-columns:90px 1fr 70px;gap:8px;align-items:center;margin:4px 0;font-size:.75rem">'
                 f'<span class="muted">{esc(role)}</span><div class="bar"><i style="width:{w}%;background:{palette.get(role, GREY)}"></i></div>'
                 f'<span class="mono">{int(v["model_calls"])}c · {int(v["tokens"])}t</span></div>')
    return rows


# ---------------------------------------------------------------------------------------------- audit flight recorder
def actor_color(who: str) -> str:
    if who in ("intake", "documents", "compliance", "finance", "followup"):
        return CYAN
    return {"reviewer": VIOLET, "supervisor": PINK, "system": GREY}.get(who, AMBER)


def timeline(entries: list[dict], flip: bool = False) -> str:
    """flip alternates the animation name so pressing Replay restarts the staggered reveal."""
    anim = "rise2" if flip else "rise"
    out = []
    for i, e in enumerate(entries):
        c = actor_color(e["who"])
        evid = f'<div class="evi">{esc(e["evidence"])}</div>' if e["evidence"] else ""
        out.append(f'<div class="ev" style="--c:{c};--i:{i};animation-name:{anim}"><span class="who">{esc(e["who"])}</span> '
                   f'<span class="tiny mono">&nbsp;{esc(e["at"][11:19])} · {esc(e["event"])}</span>'
                   f'<div class="det">{esc(e["detail"])}</div>{evid}'
                   f'<span class="hash mono">⛓ {esc(e["hash"][:10])}</span><span class="hash mono" style="color:{GREY};background:transparent;border-color:rgba(255,255,255,.12)">← {esc(e["prev"][:10])}</span></div>')
    return '<div class="tl">' + "".join(out) + "</div>"


# ---------------------------------------------------------------------------------------------- evaluation arena
def _cell(expected: str, got: str | None) -> tuple[str, str, str]:
    if got == expected:
        return GREEN, "✓", f"right: {got}"
    if got == "stop for a person" and expected == "reject":
        return AMBER, "~", "safe miss: a person looks at a case that should be rejected"
    return RED, "✕", f"expected {expected}, got {got}"


def heatmap(per_case: list[dict], key: str) -> str:
    cells = ""
    for c in per_case:
        col, mark, tip = _cell(c["expected"], c[key])
        cells += f'<div class="cell" style="background:{col}" title="{esc(c["id"])}: {esc(tip)}">{esc(c["id"][4:])}</div>'
    return f'<div class="heat">{cells}</div>'


def arena(res: dict) -> str:
    a, b = res["single"], res["team"]

    def bar(value, top, col, text):
        return f'<div class="bar"><i style="width:{max(3, 100 * value / top if top else 3):.0f}%;background:{col}"></i><em>{esc(text)}</em></div>'

    metrics = [("Decisions right", a["decisions_right"], b["decisions_right"], True, "{}/" + str(a["cases"])),
               ("Unsafe misses", a["unsafe_misses"], b["unsafe_misses"], False, "{}"),
               ("Missing items found", a["missing_items_found"], b["missing_items_found"], True, "{}/" + str(a["cases"])),
               ("Model calls per case", a["model_calls_per_case"], b["model_calls_per_case"], False, "{}"),
               ("Tokens per case", a["tokens_per_case"], b["tokens_per_case"], False, "{:,}"),
               ("Injection cases handled", a["injection_handled"], b["injection_handled"], True, "{}/" + str(a["injection_cases"]))]
    rows = ""
    for label, x, y, higher, fmt in metrics:
        top = max(x, y, 1)
        win_a = (x > y) if higher else (x < y)
        win_b = (y > x) if higher else (y < x)
        rows += (f'<div class="row"><span>{esc(label)}</span>{bar(x, top, CYAN if not win_b else "#2f7f93", ("👑 " if win_a else "") + fmt.format(x))}'
                 f'{bar(y, top, PINK if not win_a else "#8d3b63", ("👑 " if win_b else "") + fmt.format(y))}</div>')
    return (f'<div class="duel"><div class="fighter" style="background:linear-gradient(160deg,rgba(56,232,255,.18),transparent)">'
            f'<h3 style="color:{CYAN}">SINGLE AGENT</h3><div class="big" style="color:{CYAN}">{a["decisions_right"]}/{a["cases"]}</div>'
            f'<div class="tiny">one model, six tools, {a["model_calls_per_case"]} calls a case</div></div><div class="vs">VS</div>'
            f'<div class="fighter" style="background:linear-gradient(160deg,rgba(255,95,162,.18),transparent)">'
            f'<h3 style="color:{PINK}">THE TEAM</h3><div class="big" style="color:{PINK}">{b["decisions_right"]}/{b["cases"]}</div>'
            f'<div class="tiny">supervisor, 5 specialists, code reviewer, {b["model_calls_per_case"]} calls a case</div></div></div>'
            f'<div class="bars glass" style="margin-top:12px"><div class="row tiny"><span></span><span style="color:{CYAN}">single agent</span>'
            f'<span style="color:{PINK}">team</span></div>{rows}</div>')


def live_runs() -> str:
    return '<div class="runs">' + "".join(
        f'<div class="runchip" style="border-top:3px solid {c}"><div class="tiny">{esc(t)}</div><b style="color:{c}">{esc(a)}</b>'
        f'<div class="muted" style="font-size:.78rem">{esc(b)}</div></div>' for t, a, b, c in LIVE_RUNS) + "</div>"


# ---------------------------------------------------------------------------------------------- red-team lab
def redteam(text: str) -> tuple[str, list[str]]:
    """(HTML with the offending phrases highlighted, names of the patterns that matched). Nothing is saved or sent."""
    spans, names = [], []
    for name, rx in safety._COMPILED:
        for m in rx.finditer(text):
            spans.append((m.start(), m.end()))
            names.append(name)
    spans.sort()
    merged = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    out, pos = "", 0
    for s, e in merged:
        out += esc(text[pos:s]) + "<mark>" + esc(text[s:e]) + "</mark>"
        pos = e
    out += esc(text[pos:])
    return f'<div class="glass mono" style="white-space:pre-wrap;font-size:.82rem">{out}</div>', sorted(set(names))


# ---------------------------------------------------------------------------------------------- name constellation
def constellation_svg(case: dict) -> str:
    """Where the applicant sits among existing vendors (left) and watch-list entries (right). Closer = more similar; the
    rings are the policy thresholds (§3, §4). Data: the top matches the compliance checks returned."""
    from vendor_desk import rules
    raw = case.get("raw") or {}
    dup, wl = raw.get("duplicate"), raw.get("watchlist")
    if not dup and not wl:
        return ""
    cx, cy, rmax = 310, 215, 200

    def dist(score, same_tax=False):
        return 36 if same_tax else min(rmax, rmax * (1 - score) / 0.45)

    def arc(r, side, color, dash=""):
        sweep = 0 if side == "L" else 1
        return (f'<path d="M {cx} {cy - r:.1f} A {r:.1f} {r:.1f} 0 0 {sweep} {cx} {cy + r:.1f}" fill="none" stroke="{color}" '
                f'stroke-width="1.4" stroke-dasharray="{dash}"/>')

    out = ['<svg viewBox="0 0 620 430" width="100%">',
           f'<defs><clipPath id="halfL"><rect x="0" y="0" width="{cx}" height="430"/></clipPath>'
           f'<clipPath id="halfR"><rect x="{cx}" y="0" width="310" height="430"/></clipPath></defs>']
    for side, hit, near in (("L", rules.DUPLICATE_SCORE, rules.POSSIBLE_DUPLICATE_SCORE), ("R", rules.WATCHLIST_HIT_SCORE, rules.WATCHLIST_NEAR_SCORE)):
        rh, rn = dist(hit), dist(near)
        flip = -1 if side == "L" else 1
        anchor = "end" if side == "L" else "start"
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{rn:.1f}" fill="rgba(255,200,87,.07)" clip-path="url(#half{side})"/>'
                   f'<circle cx="{cx}" cy="{cy}" r="{rh:.1f}" fill="rgba(255,92,112,.13)" clip-path="url(#half{side})"/>')
        out.append(arc(rn, side, AMBER, "4 4") + arc(rh, side, RED))
        out.append(f'<text x="{cx + flip * (rn + 6):.0f}" y="{cy - 8}" font-size="9" fill="{AMBER}" text-anchor="{anchor}">a person looks ≥{near}</text>')
        out.append(f'<text x="{cx + flip * (rh + 6):.0f}" y="{cy + 14}" font-size="9" fill="{RED}" text-anchor="{anchor}">{"duplicate" if side == "L" else "hit"} ≥{hit}</text>')

    def place(items, side, kind):
        nodes = []
        n = min(len(items), 3)
        for i, m in enumerate(items[:3]):
            span = 110
            ang = (180 if side == "L" else 0) + (-span / 2 + span * (i + 0.5) / n) * (-1 if side == "L" else 1)
            d = dist(m["score"], m.get("same_tax_id", False))
            x, y = cx + d * math.cos(math.radians(ang)), cy + d * math.sin(math.radians(ang))
            if m.get("same_tax_id"):
                col = RED
            elif kind == "wl":
                col = RED if m["score"] >= rules.WATCHLIST_HIT_SCORE else AMBER if m["score"] >= rules.WATCHLIST_NEAR_SCORE else PINK
            else:
                col = RED if m["score"] >= rules.DUPLICATE_SCORE else AMBER if m["score"] >= rules.POSSIBLE_DUPLICATE_SCORE else VIOLET
            nodes.append((x, y, col, m))
        return nodes

    for x, y, col, m in place((dup or {}).get("matches", []), "L", "v") + place((wl or {}).get("matches", []), "R", "wl"):
        extra = " · same tax ID" if m.get("same_tax_id") else ""
        out.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{col}" stroke-opacity=".45" stroke-width="1.4" stroke-dasharray="3 5"/>'
                   f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{col}" fill-opacity=".85" stroke="#fff" stroke-opacity=".6"/>'
                   f'<text x="{x:.1f}" y="{y - 14:.1f}" text-anchor="middle" font-size="10" fill="#e8eaff">{esc(m["name"][:24])}</text>'
                   f'<text x="{x:.1f}" y="{y + 22:.1f}" text-anchor="middle" font-size="9" fill="{col}">{m["score"]:.2f}{extra}</text>')
    shared = (raw.get("bank") or {}).get("account_used_by_other_vendor")
    if shared:
        out.append(f'<text x="{cx}" y="22" text-anchor="middle" font-size="11" fill="{RED}">⚠ shares a bank account with {esc(shared)}</text>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="22" fill="none" stroke="{CYAN}" class="pulse"/>'
               f'<circle cx="{cx}" cy="{cy}" r="14" fill="{CYAN}"/>'
               f'<text x="{cx}" y="{cy + 38}" text-anchor="middle" font-size="11" font-weight="700" fill="{CYAN}">{esc((case.get("vendor_name") or "applicant")[:30])}</text>'
               f'<text x="{cx - 150}" y="418" text-anchor="middle" font-size="10" fill="{GREY}">EXISTING VENDORS</text>'
               f'<text x="{cx + 150}" y="418" text-anchor="middle" font-size="10" fill="{GREY}">WATCH LIST</text></svg>')
    return "".join(out)


# ---------------------------------------------------------------------------------------------- the story of a case
STORY_ICON = {"request_received": "📨", "reply_received": "📬", "verdict": "⚖️", "decision": "🧭", "state_change": "🔀", "write": "🏦",
              "reminder": "⏰", "refused": "🚫", "draft": "✉️", "stopped": "🛑", "handoff_rejected": "🔁"}


def story(entries: list[dict]) -> str:
    """The audit trail told as a short story: only the moments that matter, in plain words."""
    lines, handoffs = [], []
    for e in entries:
        ev, who, det = e["event"], e["who"], e["detail"]
        human = actor_color(who) == AMBER
        if ev == "handoff":
            handoffs.append(who)
            continue
        if ev == "tool_call":
            continue
        if handoffs:
            lines.append(("👷", CYAN, f"{', '.join(handoffs)} each handed over a checked report"))
            handoffs = []
        icon = STORY_ICON.get(ev, "•")
        if ev == "verdict":
            text = ("The reviewer sent work back: " + det.split(": ", 1)[-1]) if det.startswith("revise") else \
                "The reviewer checked every result against its evidence and approved."
            lines.append((icon, VIOLET, text))
        elif ev == "decision" and human:
            lines.append(("🧑", AMBER, f"{who}: {det}" + (f' (“{e["evidence"]}”)' if e["evidence"] else "")))
        elif ev == "decision":
            lines.append((icon, PINK, "The team recommended: " + det.replace("recommended: ", "")))
        elif ev == "state_change":
            lines.append((icon, GREY, det.replace("->", "→")))
        else:
            lines.append((icon, AMBER if human else GREY, (f"{who}: " if human else "") + det))
    if handoffs:
        lines.append(("👷", CYAN, f"{', '.join(handoffs)} each handed over a checked report"))
    rows = "".join(f'<div style="display:flex;gap:12px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.06)">'
                   f'<span style="font-size:1.2rem">{i}</span><span style="border-left:3px solid {c};padding-left:10px;font-size:.84rem">{esc(t)}</span></div>'
                   for i, c, t in lines)
    return f'<div class="glass">{rows}</div>'


# ---------------------------------------------------------------------------------------------- policy ladder (what-if lab)
def ladder(rung: int, flags: list[str]) -> str:
    from vendor_desk.whatif import LADDER
    cols = [RED, AMBER, "#ff9a4d", GREEN]
    steps = ""
    for i, (sec, label, why, fl) in enumerate(LADDER):
        on = i == rung
        hit = [f for f in flags if f in fl]
        chips_html = "".join(f'<span class="chip">{esc(f.replace("_", " "))}</span>' for f in hit)
        glow = f"box-shadow:0 0 22px {cols[i]}55;" if on else ""
        steps += (f'<div style="display:flex;align-items:center;gap:12px;padding:10px 14px;margin:6px 0;border-radius:12px;'
                  f'border:1px solid {cols[i] if on else "rgba(255,255,255,.08)"};background:{cols[i] + "22" if on else "rgba(255,255,255,.03)"};'
                  f'opacity:{1 if on or i > rung else .45};{glow}">'
                  f'<span class="mono" style="color:{cols[i]};font-weight:800">{sec}</span>'
                  f'<span style="flex:1"><b style="color:{cols[i]}">{label}</b><br><span class="muted" style="font-size:.76rem">if {esc(why)}</span></span>'
                  f'<span>{chips_html}{"◀ the first rule that applies" if on else ""}</span></div>')
    return steps
