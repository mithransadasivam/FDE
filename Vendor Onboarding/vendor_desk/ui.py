"""The Docket: a detective's case-file look for the app. Pure functions that turn case data into HTML / inline SVG.

  Inbox      manila folders on a walnut desk, a typed memo, a paper ticker tape
  Case       a corkboard: polaroid, index cards, newspaper clippings, red string; an approval slip with signature lines
  Audit      a typewriter paper roll that types itself out
  Evaluation a race over 19 gates
  Rulebook   a marble run through the policy rules
  Red team   an evidence bag with the attack circled in marker

Nothing here talks to a model or a database. Every value that came from an email, a document or a vendor name goes through
esc() before it is placed in markup, so a vendor called "<script>" is shown as text, never run (tests/test_ui.py).
"""
import html
import math
import re
import textwrap

from vendor_desk import safety

INK, PAPER, CARD, MANILA = "#2a2118", "#f4ecd8", "#fffaf0", "#e6c677"
RED, BLUE, GREEN, AMBER, GREY, CORK = "#b3261e", "#1f4e8c", "#3d7a47", "#b97d00", "#7a6f5d", "#c9a26e"
TYPE = "'Courier New', 'American Typewriter', Courier, monospace"
HAND = "'Segoe Script', 'Bradley Hand', 'Comic Sans MS', cursive"

STATUS_STAMP = {"RECEIVED": ("INCOMING", GREY), "CHECKING": ("CHECKING", BLUE), "WAITING_FOR_VENDOR": ("AWAITING VENDOR", AMBER),
                "READY_FOR_APPROVAL": ("READY TO SIGN", BLUE), "APPROVED": ("APPROVED", GREEN), "CREATED": ("APPROVED & FILED", GREEN),
                "REJECTED": ("DENIED", RED), "STOPPED": ("ON HOLD", RED)}
RESULT_STAMP = {"pass": ("CLEAR", GREEN), "review": ("LOOK AT THIS", AMBER), "fail": ("FAIL", RED), "missing": ("MISSING", RED)}
STRING_COLOR = {"pass": "#5b7d4a", "review": "#d29a00", "fail": RED, "missing": "#d9534f"}
CHECK_LABEL = {"documents": "DOCUMENTS", "duplicate": "EXISTING VENDOR?", "watchlist": "WATCH LIST", "payment_terms": "PAYMENT TERMS",
               "bank": "BANK DETAILS", "spend": "SPEND"}
FLAG_WEIGHT = {"duplicate_vendor": 95, "watchlist_hit": 95, "possible_injection": 85, "bank_account_shared": 80,
               "watchlist_near_match": 75, "bank_holder_mismatch": 75, "possible_duplicate": 70, "bank_country_mismatch": 65,
               "insurance_expired": 35, "payment_terms_over_limit": 30}
LIVE_RUNS = [  # the live-model runs (see EVAL_REPORT.md)
    ("RUN 1", "Haiku 19/19", "11 review problems", GREEN),
    ("RUN 2", "Haiku 18/19", "fooled by the 'skip the checks' email", RED),
    ("RUN 3", "cut short", "API key limit reached", AMBER),
    ("RUN 4", "DeepSeek 19/19", "single agent and team both clean", GREEN),
]


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def wrap(text: str, width: int, max_lines: int) -> list[str]:
    lines = textwrap.wrap(str(text), width) or [""]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][:max(0, width - 1)].rstrip() + "…"
    return lines


def initials(name: str) -> str:
    words = [w for w in re.split(r"\W+", name or "") if w and w.lower() not in ("ltd", "limited", "plc", "gmbh", "llp", "co")]
    return "".join(w[0] for w in words[:2]).upper() or "?"


def risk_score(case: dict) -> int:
    scores = [FLAG_WEIGHT[f] for f in case.get("flags", []) if f in FLAG_WEIGHT]
    if case.get("missing_items"):
        scores.append(30)
    if not scores:
        return 6 if case.get("checks") else 0
    return min(100, max(scores) + 4 * (len(scores) - 1))


def risk_color(score: int) -> str:
    return GREEN if score < 25 else AMBER if score < 50 else "#c2571a" if score < 75 else RED


def stamp_for(case: dict) -> tuple[str, str]:
    label, color = STATUS_STAMP.get(case["status"], ("FILE", GREY))
    if case["status"] == "STOPPED" and case.get("decision") == "reject":
        label = "RECOMMEND: DENY"
    return label, color


# ---------------------------------------------------------------------------------------------- global theme
_CSS = """
<style>
.stApp { background:
   repeating-linear-gradient(90deg, rgba(0,0,0,.07) 0 2px, transparent 2px 9px),
   repeating-linear-gradient(90deg, rgba(255,255,255,.025) 0 1px, transparent 1px 23px),
   radial-gradient(1200px 700px at 50% -10%, rgba(255,214,150,.30), transparent 60%),
   linear-gradient(#5a3b26, #331f12); }
[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 1280px; margin: 1.4rem auto 2.4rem; padding: 2.2rem 2.6rem 3rem !important; background:
   radial-gradient(900px 400px at 20% 0%, rgba(255,255,255,.55), transparent 70%),
   repeating-linear-gradient(0deg, rgba(120,90,40,.035) 0 1px, transparent 1px 4px), %PAPER%;
   border-radius: 4px; box-shadow: 0 30px 70px rgba(0,0,0,.55), inset 0 0 0 1px rgba(120,90,40,.25); color:%INK%; }
html, body, [class*="css"], .stMarkdown, p, li, label, .stCaption { color:%INK%; }
h1,h2,h3,h4,h5 { font-family: %TYPE%; letter-spacing:.04em; color:%INK% !important; }
[data-testid="stSidebar"] { background: linear-gradient(180deg,#2a1b12,#1b1009); border-right: 4px solid #0e0804; }
[data-testid="stSidebar"] * { color:#f1e6cc !important; }
[data-testid="stSidebar"] input { color:%INK% !important; }
[data-testid="stSidebar"] .stButton button, [data-testid="stSidebar"] .stButton button * { color:%INK% !important; }
.tw { font-family: %TYPE%; } .hand { font-family: %HAND%; }
.tiny { font-size:.7rem; letter-spacing:.14em; text-transform:uppercase; opacity:.7; font-family:%TYPE%; }

/* masthead */
.mast { text-align:center; border-top:5px double %INK%; border-bottom:5px double %INK%; padding:8px 0 10px; margin-bottom:12px; }
.mast .t { font-family: Georgia,'Times New Roman',serif; font-weight:900; font-size:3.1rem; letter-spacing:.22em; line-height:1.05; }
.mast .s { font-family:%TYPE%; font-size:.78rem; letter-spacing:.18em; text-transform:uppercase; margin-top:4px; display:flex; justify-content:space-between; border-top:1px solid %INK%; padding-top:5px; }

/* paper ticker tape */
.tape { overflow:hidden; white-space:nowrap; background:#f6efc9; border-top:2px dashed #b9a96a; border-bottom:2px dashed #b9a96a; margin:6px 0 16px; box-shadow:0 2px 4px rgba(0,0,0,.15); }
.tape .belt { display:inline-block; padding:5px 0; animation: belt 90s linear infinite; font-family:%TYPE%; font-size:.76rem; }
.tape:hover .belt { animation-play-state: paused; }
@keyframes belt { from { transform: translateX(0); } to { transform: translateX(-50%); } }
.tape span { margin:0 26px; } .tape b { color:%RED%; }

/* memo */
.memo { position:relative; background:#fffdf3; border:1px solid #d9cdb0; padding:18px 24px 16px; margin-bottom:14px; box-shadow:2px 3px 0 rgba(0,0,0,.12); transform:rotate(-.4deg); font-family:%TYPE%; }
.memo .l { font-size:.95rem; line-height:1.7; overflow:hidden; white-space:nowrap; animation: typeline 1.1s steps(60) both; animation-delay: calc(var(--i) * .35s); }
@keyframes typeline { from { clip-path: inset(0 100% 0 0); } to { clip-path: inset(0 0 0 0); } }
.memo .l b { background: linear-gradient(transparent 55%, rgba(230,198,119,.8) 55%); }
.memo .rs { position:absolute; right:22px; top:16px; transform:rotate(9deg); }

/* rubber stamps */
.rs { display:inline-block; border:3px double var(--c); color:var(--c); padding:2px 12px; font-family:%TYPE%; font-weight:900; letter-spacing:.16em; text-transform:uppercase;
  font-size:.86rem; opacity:.9; mix-blend-mode:multiply; animation: slam .45s ease-out both; }
@keyframes slam { from { transform: scale(2.2) rotate(-14deg); opacity:0; } to { opacity:.9; } }

/* folders */
.folder { position:relative; margin: 20px 4px 4px; transform: rotate(var(--rot)); transition: transform .2s; }
.folder:hover { transform: rotate(0deg) translateY(-4px); }
.ftab { position:absolute; top:-20px; left:14px; background:%MANILA%; border:2px solid #9a7b2f; border-bottom:none; border-radius:8px 8px 0 0; padding:2px 14px; font-family:%TYPE%; font-weight:900; letter-spacing:.1em; font-size:.8rem; box-shadow: inset 0 -3px 0 rgba(0,0,0,.05); }
.fbody { background: linear-gradient(160deg, #efd48c, %MANILA%); border:2px solid #9a7b2f; border-radius:0 8px 8px 8px; padding:18px 14px 16px; min-height:216px; box-shadow: 4px 6px 0 rgba(0,0,0,.2); position:relative; }
.fbody::after { content:""; position:absolute; left:6px; right:6px; bottom:5px; height:2px; background: repeating-linear-gradient(90deg, rgba(0,0,0,.25) 0 6px, transparent 6px 10px); }
.fname { font-family: Georgia,serif; font-weight:900; font-size:1.04rem; line-height:1.15; padding-right:4px; }
.fnext { font-family:%TYPE%; font-size:.72rem; margin-top:8px; line-height:1.35; opacity:.85; }
.fheat { height:9px; border:1.5px solid %INK%; background:#fff8e1; margin-top:9px; border-radius:2px; overflow:hidden; }
.fheat i { display:block; height:100%; background: repeating-linear-gradient(135deg, var(--c) 0 6px, rgba(255,255,255,.35) 6px 9px); }
.fchip { display:inline-block; font-family:%TYPE%; font-size:.64rem; background:#fff8e1; border:1px dashed %RED%; color:%RED%; padding:0 6px; margin:3px 4px 0 0; border-radius:2px; }
.folder .rs { display:inline-block; margin-top:10px; font-size:.7rem; transform: rotate(-3deg); background: rgba(255,250,240,.35); }
.clip { position:absolute; right:14px; top:-10px; width:18px; height:46px; border:2.5px solid #8a8a93; border-radius:9px; background:transparent; z-index:3; }
.clip::after { content:""; position:absolute; left:3px; right:3px; top:8px; bottom:-8px; border:2.5px solid #8a8a93; border-radius:9px; }

/* buttons */
.stButton > button { background:%CARD%; color:%INK% !important; border:2px solid %INK%; border-radius:3px; box-shadow:3px 3px 0 %INK%; font-family:%TYPE%; font-weight:700; transition: transform .08s, box-shadow .08s; }
.stButton > button:hover { transform: translate(-1px,-1px); box-shadow:4px 4px 0 %INK%; background:#fff3cf; border-color:%INK%; }
.stButton > button:active { transform: translate(2px,2px); box-shadow:1px 1px 0 %INK%; }
.stButton > button[kind="primary"] { background:%RED%; color:#fff !important; border-color:#7d1a14; box-shadow:3px 3px 0 #7d1a14; }
[class*="st-key-act_"] button { height:62px; font-size:1.02rem !important; letter-spacing:.14em; text-transform:uppercase; background:transparent !important; border:4px double var(--c) !important;
   color:var(--c) !important; box-shadow:none !important; transform:rotate(-1.5deg); mix-blend-mode:multiply; }
[class*="st-key-act_"] button:hover { background: rgba(255,255,255,.4) !important; transform: rotate(0deg) scale(1.03); }
[class*="st-key-act_approve"] { --c:%GREEN%; } [class*="st-key-act_reject"] { --c:%RED%; } [class*="st-key-act_ask"] { --c:%BLUE%; }
[class*="st-key-act_release"] { --c:%GREEN%; } [class*="st-key-act_rerun"] { --c:%GREY%; }
[class*="st-key-sig_"] input { font-family:%HAND%; font-size:1.35rem; color:#1c3f8a !important; background:transparent !important; border:none !important; border-bottom:2px solid %INK% !important; border-radius:0 !important; padding-left:4px; }
[class*="st-key-sig_"] input::placeholder { color:#b9a96a; font-size:.95rem; }
[data-testid="stButtonGroup"] button { background:#e3c97f !important; border:2px solid #9a7b2f !important; border-bottom:none !important; border-radius:8px 8px 0 0 !important; font-family:%TYPE%; font-weight:800; color:%INK% !important; margin-right:3px; }
[data-testid="stButtonGroup"] button[aria-checked="true"], [data-testid="stButtonGroup"] button[kind="segmented_controlActive"] { background:%CARD% !important; box-shadow: 0 -3px 0 %RED% inset; }
input, textarea, [data-baseweb="select"] > div { background:#fffdf5 !important; color:%INK% !important; border-color:#c9b88f !important; font-family:%TYPE%; }

/* approval slip */
.slip { background:#fffdf3; border:1px solid #d9cdb0; padding:16px 20px; font-family:%TYPE%; box-shadow:3px 4px 0 rgba(0,0,0,.14); transform:rotate(.5deg); position:relative; }
.slip .sh { margin:0 0 8px; border-bottom:2px solid %INK%; padding-bottom:4px; font-size:1rem; font-weight:900; letter-spacing:.12em; display:flex; justify-content:space-between; }
.slip .ln { font-size:.84rem; line-height:1.7; border-bottom:1px dotted #b9a96a; }
.sig { display:inline-block; width:46%; min-width:190px; margin:12px 2% 4px 0; border-bottom:2px solid %INK%; min-height:46px; position:relative; vertical-align:bottom; }
.sig .who { font-family:%HAND%; font-size:1.25rem; color:#1c3f8a; transform:rotate(-3deg); display:block; }
.sig .cap { font-size:.62rem; letter-spacing:.12em; text-transform:uppercase; opacity:.65; position:absolute; bottom:-16px; left:0; }
.sig.empty .who { color:#b9a96a; font-size:.9rem; } .sig .x { position:absolute; left:-2px; bottom:2px; font-size:1rem; opacity:.6; }
.wax { display:inline-grid; place-items:center; width:92px; height:92px; border-radius:50%; color:#ffd9d4; font-family:%TYPE%; font-weight:900; font-size:.74rem; letter-spacing:.06em; text-align:center;
  background: radial-gradient(circle at 35% 30%, #d9483c, #8c1b13 70%); box-shadow: 0 4px 8px rgba(0,0,0,.4), inset 0 0 0 5px rgba(255,255,255,.12); animation: press .6s ease-out both; }
@keyframes press { from { transform: scale(1.6); opacity:0; } to { transform:none; opacity:1; } }
.lock { font-family:%TYPE%; font-size:.78rem; opacity:.85; }

/* typewriter roll */
.roll { max-width:820px; margin:0 auto; background:#fffefa; padding:26px 26px 30px; box-shadow:0 8px 22px rgba(0,0,0,.28); font-family:%TYPE%; position:relative;
  clip-path: polygon(0 8px,2% 0,4% 8px,6% 0,8% 8px,10% 0,12% 8px,14% 0,16% 8px,18% 0,20% 8px,22% 0,24% 8px,26% 0,28% 8px,30% 0,32% 8px,34% 0,36% 8px,38% 0,40% 8px,42% 0,44% 8px,46% 0,48% 8px,50% 0,52% 8px,54% 0,56% 8px,58% 0,60% 8px,62% 0,64% 8px,66% 0,68% 8px,70% 0,72% 8px,74% 0,76% 8px,78% 0,80% 8px,82% 0,84% 8px,86% 0,88% 8px,90% 0,92% 8px,94% 0,96% 8px,98% 0,100% 8px,100% calc(100% - 8px),98% 100%,96% calc(100% - 8px),94% 100%,92% calc(100% - 8px),90% 100%,88% calc(100% - 8px),86% 100%,84% calc(100% - 8px),82% 100%,80% calc(100% - 8px),78% 100%,76% calc(100% - 8px),74% 100%,72% calc(100% - 8px),70% 100%,68% calc(100% - 8px),66% 100%,64% calc(100% - 8px),62% 100%,60% calc(100% - 8px),58% 100%,56% calc(100% - 8px),54% 100%,52% calc(100% - 8px),50% 100%,48% calc(100% - 8px),46% 100%,44% calc(100% - 8px),42% 100%,40% calc(100% - 8px),38% 100%,36% calc(100% - 8px),34% 100%,32% calc(100% - 8px),30% 100%,28% calc(100% - 8px),26% 100%,24% calc(100% - 8px),22% 100%,20% calc(100% - 8px),18% 100%,16% calc(100% - 8px),14% 100%,12% calc(100% - 8px),10% 100%,8% calc(100% - 8px),6% 100%,4% calc(100% - 8px),2% 100%,0 calc(100% - 8px)); }
.rl { display:grid; grid-template-columns: 38px 70px 112px 1fr 84px; gap:8px; padding:5px 0; border-bottom:1px dotted #cdbf9b; font-size:.8rem; line-height:1.4; }
.rl .n { opacity:.45; } .rl .w { font-weight:900; } .rl .h { color:#2a6f8f; font-size:.68rem; text-align:right; }
.rl .d { overflow:hidden; clip-path: inset(0 100% 0 0); animation: typeline 1.1s steps(40) forwards; animation-delay: calc(var(--i) * .18s); animation-name: typeline; }
.rl .d.f2 { animation-name: typeline2; }
@keyframes typeline2 { from { clip-path: inset(0 100% 0 0); } to { clip-path: inset(0 0 0 0); } }
.rl .e { display:block; font-size:.68rem; opacity:.6; }

/* paper bits */
.receipt { background:#fffefa; font-family:%TYPE%; font-size:.76rem; padding:12px 14px 16px; box-shadow:2px 3px 0 rgba(0,0,0,.14); border-top:6px solid #fffefa; }
.receipt .r { display:flex; justify-content:space-between; border-bottom:1px dotted #cdbf9b; padding:2px 0; }
.letter { background:#fffdf3; border:1px solid #d9cdb0; padding:16px 18px; font-family:Georgia,serif; font-size:.82rem; line-height:1.55; white-space:pre-wrap; box-shadow:3px 4px 0 rgba(0,0,0,.14); transform:rotate(-.5deg); position:relative; }
.note { font-family:%HAND%; background:#fff3a3; padding:12px 14px; box-shadow:3px 4px 0 rgba(0,0,0,.18); transform:rotate(1.2deg); font-size:.92rem; line-height:1.5; position:relative; }
.note::before { content:""; position:absolute; top:-9px; left:38%; width:70px; height:18px; background:rgba(255,255,255,.55); transform:rotate(-3deg); box-shadow:0 1px 2px rgba(0,0,0,.2); }
.story { font-family:%HAND%; font-size:.95rem; line-height:1.7; }
.story div { padding:3px 0; border-bottom:1px solid rgba(120,90,40,.2); }

/* split-flap scoreboard */
.flap { display:inline-block; min-width:26px; padding:5px 4px; margin:1px; text-align:center; background:linear-gradient(#2d2d2d 49%, #151515 51%); color:#f3f3f3; font-family:%TYPE%; font-weight:900; font-size:1.25rem; border-radius:3px; box-shadow:0 2px 0 #000; position:relative; }
.flap.win { color:#ffd54a; box-shadow:0 0 0 2px #ffd54a, 0 2px 0 #000; }
.score { display:grid; grid-template-columns: 190px 1fr 1fr; gap:10px; align-items:center; padding:8px 0; border-bottom:1px dotted #b9a96a; font-family:%TYPE%; font-size:.8rem; }
.hist { display:flex; gap:10px; flex-wrap:wrap; }
.hist div { flex:1; min-width:170px; border:2px solid %INK%; padding:8px 12px; background:%CARD%; box-shadow:3px 3px 0 %INK%; font-family:%TYPE%; font-size:.78rem; }

/* red team */
.bag { position:relative; border:3px solid rgba(60,90,110,.55); background: linear-gradient(135deg, rgba(190,220,235,.35), rgba(255,255,255,.25)); padding:30px 18px 16px; border-radius:6px; font-family:%TYPE%; font-size:.84rem; white-space:pre-wrap; }
.bag::before { content:"EVIDENCE · DO NOT OPEN"; position:absolute; top:-3px; left:-3px; right:-3px; background:repeating-linear-gradient(45deg,#d9a400 0 12px,#2a2118 12px 24px); color:#fff; font-weight:900; letter-spacing:.2em; font-size:.66rem; text-align:center; padding:3px; text-shadow:0 0 3px #000; }
mark { background: linear-gradient(transparent 50%, rgba(179,38,30,.38) 50%); box-shadow:0 0 0 2px rgba(179,38,30,.7); border-radius: 45% 55% 50% 50% / 60% 40% 60% 40%; padding:0 4px; color:inherit; }
</style>
"""

CSS = _CSS
for _k, _v in {"%PAPER%": PAPER, "%INK%": INK, "%TYPE%": TYPE, "%HAND%": HAND, "%MANILA%": MANILA, "%RED%": RED, "%GREEN%": GREEN,
               "%BLUE%": BLUE, "%GREY%": GREY, "%CARD%": CARD}.items():
    CSS = CSS.replace(_k, _v)


# ---------------------------------------------------------------------------------------------- masthead, memo, tape
def masthead(n_files: int, today: str) -> str:
    return ('<div class="mast"><div class="t">THE DOCKET</div>'
            f'<div class="s"><span>vendor onboarding</span><span>agents check · a person signs</span><span>{esc(today)} · {n_files} files</span></div></div>')


def memo(cases: list[dict]) -> str:
    human = sum(1 for c in cases if c["status"] in ("READY_FOR_APPROVAL", "STOPPED"))
    waiting = sum(1 for c in cases if c["status"] == "WAITING_FOR_VENDOR")
    filed = sum(1 for c in cases if c["status"] == "CREATED")
    inj = sum(1 for c in cases if c.get("injection"))
    calls = int(sum(c["usage"]["model_calls"] for c in cases))
    lines = [("TO:", "you, the person who signs"), ("FROM:", "the desk (5 agents, 1 code reviewer, no authority)"),
             ("RE:", f"<b>{len(cases)} files</b> on the desk"),
             ("", f"<b>{human}</b> need a person · <b>{waiting}</b> wait on a vendor · <b>{filed}</b> filed today"),
             ("", f"<b>{inj}</b> emails tried to give orders (ignored) · {calls} model calls spent")]
    rows = "".join(f'<div class="l" style="--i:{i}"><span style="display:inline-block;width:64px;font-weight:900">{k}</span>{v}</div>' for i, (k, v) in enumerate(lines))
    return f'<div class="memo"><span class="rs" style="--c:{RED}">confidential</span>{rows}</div>'


def tape(events: list[dict]) -> str:
    if not events:
        return ""
    items = "".join(f'<span><b>{esc(e["case_id"])}</b> {esc(e["at"][11:19])} {esc(e["who"])}: {esc(e["detail"][:80])}</span>' for e in events)
    return f'<div class="tape"><div class="belt">{items}{items}</div></div>'


# ---------------------------------------------------------------------------------------------- inbox: folders
def folder(case: dict) -> str:
    label, color = stamp_for(case)
    score = risk_score(case)
    num = int(re.sub(r"\D", "", case["case_id"]) or 0)
    rot = ((num * 37) % 5 - 2) * 0.7
    chips = "".join(f'<span class="fchip">{esc(f.replace("_", " "))}</span>' for f in case["flags"][:3])
    sigs = ""
    if case.get("approvers_required"):
        n, need = len(case["approvals"]), case["approvers_required"]
        sigs = f'<div class="fnext">{"✍ " * n}{"▫ " * (need - n)} {n}/{need} signatures</div>'
    return (f'<div class="folder" style="--rot:{rot}deg"><div class="ftab">{esc(case["case_id"])}</div><div class="clip"></div>'
            f'<div class="fbody"><div class="fname">{esc(case["vendor_name"] or case["subject"])}</div>{chips}{sigs}'
            f'<div class="fnext">{esc(case["next_step"][:105])}</div>'
            f'<div class="fheat" title="risk {score}"><i style="width:{max(score, 4)}%;--c:{risk_color(score)}"></i></div>'
            f'<span class="rs" style="--c:{color}">{esc(label)}</span></div></div>')


# ---------------------------------------------------------------------------------------------- the desk line (live theater)
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
    if status == "READY_FOR_APPROVAL" or (status == "STOPPED" and case.get("decision")):
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


DESKS = [("intake", "INTAKE", "📨"), ("documents", "DOCUMENTS", "📄"), ("finance", "FINANCE", "💷"), ("compliance", "COMPLIANCE", "🕵️"),
         ("reviewer", "REVIEWER", "⚖️"), ("gate", "YOU", "🖋️"), ("vault", "FILED", "🗄️")]
_DESK_X = [80 + i * 140 for i in range(7)]


def desk_index(active: tuple, state: dict) -> int | None:
    for i, (key, _, _) in enumerate(DESKS):
        if key in active:
            return i
    if state.get("gate") in ("wait", "pause"):
        return 5
    if state.get("vault") == "done":
        return 6
    return None


def desk_line(case: dict, active: tuple = (), prev: int | None = None) -> str:
    """Seven desks in a row; the manila folder sits at the desk where the case is (and slides there from the previous one)."""
    st = station_states(case)
    for k in active:
        if k in st:
            st[k] = "active"
    here = desk_index(active, st)
    parts = ['<svg viewBox="0 0 1000 150" width="100%"><defs><filter id="ds"><feDropShadow dx="2" dy="3" stdDeviation="2" flood-opacity=".3"/></filter></defs>',
             f'<line x1="40" y1="96" x2="960" y2="96" stroke="{INK}" stroke-width="2" stroke-dasharray="3 7" opacity=".45"/>']
    for (key, label, icon), x in zip(DESKS, _DESK_X):
        s = st.get(key, "idle")
        col = {"done": GREEN, "wait": BLUE, "pause": AMBER, "fail": RED, "idle": "#a89b7d", "active": RED}[s]
        mark = {"done": "✔", "wait": "SIGN", "pause": "…", "fail": "✖", "idle": "", "active": "…"}[s]
        parts.append(f'<g filter="url(#ds)"><rect x="{x - 48}" y="84" width="96" height="36" rx="3" fill="#8a5a33" stroke="#4a2f1a"/>'
                     f'<rect x="{x - 48}" y="80" width="96" height="9" fill="#a8744a" stroke="#4a2f1a"/></g>'
                     f'<text x="{x}" y="58" text-anchor="middle" font-size="26">{icon}</text>'
                     f'<text x="{x}" y="140" text-anchor="middle" font-size="10" font-weight="900" letter-spacing="1.4" fill="{INK}" font-family="{TYPE}">{label}</text>'
                     f'<g transform="rotate(-9 {x + 30} 38)"><text x="{x + 30}" y="42" text-anchor="middle" font-size="11" font-weight="900" fill="{col}" font-family="{TYPE}" '
                     f'stroke="{col}" stroke-width=".3">{mark}</text></g>')
        if s in ("done", "fail", "wait", "pause"):
            parts.append(f'<circle cx="{x + 30}" cy="37" r="16" fill="none" stroke="{col}" stroke-width="2.2" stroke-dasharray="4 2" opacity=".85"/>')
    if here is not None:
        x1 = _DESK_X[prev if prev is not None else here]
        x2 = _DESK_X[here]
        slide = (f'<animateTransform attributeName="transform" type="translate" from="{x1 - x2} 0" to="0 0" dur="0.55s" fill="freeze"/>' if x1 != x2 else "")
        parts.append(f'<g transform="translate({x2} 0)"><g>{slide}<text x="0" y="82" text-anchor="middle" font-size="34">📁</text></g></g>')
    sb = (case.get("reviewer") or {}).get("revisions", 0)
    if sb:
        parts.append(f'<text x="{(_DESK_X[3] + _DESK_X[4]) // 2}" y="22" text-anchor="middle" font-size="11" fill="{RED}" font-family="{HAND}">↩ sent back ×{sb}</text>')
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------------------------- the corkboard
def _string(x1, y1, x2, y2, color) -> str:
    dist = math.hypot(x2 - x1, y2 - y1)
    cx, cy = (x1 + x2) / 2, max(y1, y2) + 18 + dist * 0.10
    d = f"M {x1:.0f} {y1:.0f} Q {cx:.0f} {cy:.0f} {x2:.0f} {y2:.0f}"
    return (f'<path d="{d}" fill="none" stroke="rgba(0,0,0,.35)" stroke-width="3" transform="translate(2 3)"/>'
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.6" stroke-linecap="round"/>'
            f'<path d="{d}" fill="none" stroke="rgba(255,255,255,.35)" stroke-width="1" stroke-dasharray="2 5"/>')


def _pin(x, y, color="#c0392b") -> str:
    return (f'<circle cx="{x:.0f}" cy="{y:.0f}" r="7" fill="url(#pin{color[1:]})" stroke="rgba(0,0,0,.4)" stroke-width=".8"/>'
            f'<circle cx="{x - 2:.0f}" cy="{y - 2:.0f}" r="2" fill="rgba(255,255,255,.75)"/>')


def _stamp_svg(x, y, text, color, rot, size=14, w=None) -> str:
    w = w or (len(text) * size * 0.72 + 16)
    return (f'<g transform="translate({x} {y}) rotate({rot})" opacity=".92"><rect x="{-w / 2:.0f}" y="{-size:.0f}" width="{w:.0f}" height="{size * 1.7:.0f}" '
            f'fill="none" stroke="{color}" stroke-width="3" rx="2"/><rect x="{-w / 2 + 3:.0f}" y="{-size + 3:.0f}" width="{w - 6:.0f}" height="{size * 1.7 - 6:.0f}" '
            f'fill="none" stroke="{color}" stroke-width="1" rx="1"/><text x="0" y="{size * 0.32:.0f}" text-anchor="middle" font-size="{size}" font-weight="900" '
            f'letter-spacing="2" fill="{color}" font-family="{TYPE}">{esc(text)}</text></g>')


def _card(x, y, w, h, rot, title, accent, lines, foot, stamp=None, tool="") -> str:
    g = [f'<g transform="translate({x} {y}) rotate({rot} {w / 2:.0f} {h / 2:.0f})" filter="url(#shadow)">',
         f'<rect width="{w}" height="{h}" rx="2" fill="{CARD}" stroke="#d9cdb0"/>',
         f'<rect width="{w}" height="22" fill="{accent}" opacity=".9"/>',
         f'<text x="9" y="15" font-size="10.5" font-weight="900" letter-spacing="1.3" fill="#fff" font-family="{TYPE}">{esc(title)}</text>']
    for i in range(1, 8):   # ruled lines like an index card
        g.append(f'<line x1="8" x2="{w - 8}" y1="{22 + i * 17}" y2="{22 + i * 17}" stroke="#9fc1d8" stroke-width=".6" opacity=".55"/>')
    text = "".join(f'<tspan x="9" dy="{0 if i == 0 else 17}">{esc(ln)}</tspan>' for i, ln in enumerate(lines))
    g.append(f'<text x="9" y="{22 + 14}" font-size="11" fill="{INK}" font-family="{TYPE}">{text}</text>')
    g.append(f'<text x="9" y="{h - 9}" font-size="14" fill="#1c3f8a" font-family="{HAND}" transform="rotate(-2 9 {h - 9})">{esc(foot)}</text>')
    if tool:
        g.append(f'<text x="{w - 8}" y="{h - 9}" text-anchor="end" font-size="8.5" fill="{GREY}" font-family="{TYPE}">{esc(tool)}</text>')
    g.append("</g>")
    out = "".join(g)
    if stamp:
        out += f'<g transform="translate({x} {y}) rotate({rot} {w / 2:.0f} {h / 2:.0f})">{_stamp_svg(w - 66, h - 40, stamp[0], stamp[1], -8, 11)}</g>'
    return out


def board_svg(case: dict) -> str:
    """The corkboard: a polaroid of the applicant in the middle, an index card per check, newspaper clippings for the names it
    resembles, and string from the polaroid to each card (green twine = clear, yellow = look, red = fail or missing)."""
    W, H = 1000, 850
    raw = case.get("raw") or {}
    by = {c["check"]: c for c in case.get("checks", [])}
    cx, cy = 500, 330
    slots = {"documents": (28, 34, -1.6), "duplicate": (28, 250, 1.2), "watchlist": (28, 466, -1.0),
             "payment_terms": (772, 34, 1.5), "bank": (772, 250, -1.2), "spend": (772, 466, 1.1)}
    defs = ('<defs><filter id="shadow" x="-10%" y="-10%" width="125%" height="135%"><feDropShadow dx="3" dy="5" stdDeviation="3" flood-opacity=".35"/></filter>'
            '<filter id="noise"><feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" seed="7"/>'
            '<feColorMatrix type="matrix" values="0 0 0 0 .33  0 0 0 0 .20  0 0 0 0 .09  1.7 0 0 0 -.38"/></filter>'
            '<linearGradient id="cork" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#d4ae78"/><stop offset="1" stop-color="#b98f58"/></linearGradient>'
            + "".join(f'<radialGradient id="pin{c[1:]}" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#fff" stop-opacity=".9"/><stop offset=".25" stop-color="{c}"/>'
                      f'<stop offset="1" stop-color="#4a0f0a"/></radialGradient>' for c in ("#c0392b",)) + "</defs>")
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%">{defs}',
           f'<rect width="{W}" height="{H}" rx="6" fill="url(#cork)"/><rect width="{W}" height="{H}" rx="6" filter="url(#noise)"/>',
           f'<rect x="3" y="3" width="{W - 6}" height="{H - 6}" rx="6" fill="none" stroke="#5a3b22" stroke-width="10"/>']
    # strings first (under the cards)
    pins = []
    for key, (x, y, rot) in slots.items():
        c = by.get(key)
        px = x + 178            # the pin sits at the right end of the card's header strip, clear of its title
        color = STRING_COLOR.get(c["result"] if c else "", "#8a7d6a")
        out.append(_string(cx, 222, px, y + 11, color))
        pins.append((px, y + 11))
    # cards
    for key, (x, y, rot) in slots.items():
        c = by.get(key)
        if c:
            label, col = RESULT_STAMP[c["result"]]
            accent = {"pass": "#4f7a47", "review": "#b58300", "fail": "#a32218", "missing": "#a32218"}[c["result"]]
            out.append(_card(x, y, 200, 190, rot, CHECK_LABEL[key], accent, wrap(c["evidence"].split(": ", 1)[-1], 27, 6), c["policy_section"],
                             (label, col), c["tool"]))
        else:
            out.append(_card(x, y, 200, 190, rot, CHECK_LABEL[key], "#8a7d6a", ["(not run for this case)"], "—"))
    for px, py in pins:
        out.append(_pin(px, py))
    # clippings for the matches
    def clip(x, y, kind, m):
        hot = m.get("same_tax_id") or m["score"] >= 0.75
        col = RED if hot else GREY
        sub = "same tax ID" if m.get("same_tax_id") else f'similarity {m["score"]:.2f}'
        lines = wrap(m["name"], 17, 2)
        txt = "".join(f'<tspan x="8" dy="{0 if i == 0 else 15}">{esc(ln)}</tspan>' for i, ln in enumerate(lines))
        return (f'<g transform="translate({x} {y}) rotate({(x % 7) - 3})" filter="url(#shadow)"><rect width="140" height="96" fill="#ece6d3" stroke="#bdb496" stroke-dasharray="3 2"/>'
                f'<rect width="140" height="17" fill="#d6cfb6"/><text x="8" y="12" font-size="8.5" font-weight="900" letter-spacing="1.5" fill="{INK}" font-family="{TYPE}">{kind}</text>'
                f'<text x="8" y="38" font-size="12" font-weight="700" fill="{INK}" font-family="Georgia,serif">{txt}</text>'
                f'<text x="8" y="86" font-size="14" fill="{col}" font-family="{HAND}">{esc(sub)}</text></g>')
    dups, wls = (raw.get("duplicate") or {}).get("matches", [])[:3], (raw.get("watchlist") or {}).get("matches", [])[:3]
    for i, m in enumerate(dups):
        x = 30 + i * 150
        out.append(clip(x, 742, "EXISTING VENDOR", m))
        out.append(_pin(x + 70, 742))
    for i, m in enumerate(wls):
        x = 520 + i * 150
        out.append(clip(x, 742, "WATCH LIST", m))
        out.append(_pin(x + 70, 742))
    if dups or wls:
        out.append(f'<text x="30" y="732" font-size="14" fill="#3a2a16" font-family="{HAND}">the names the checks compared it with ▾</text>')
    # reviewer post-it (top centre)
    rv = case.get("reviewer")
    if rv:
        note = rv.get("notes") or "; ".join(rv.get("issues", []))
        tl = "".join(f'<tspan x="14" dy="{0 if i == 0 else 17}">{esc(ln)}</tspan>' for i, ln in enumerate(wrap(note, 34, 4)))
        out.append(f'<g transform="translate(358 34) rotate(-2.5)" filter="url(#shadow)"><rect width="284" height="118" fill="#fff3a3"/>'
                   f'<text x="14" y="36" font-size="12" font-weight="900" letter-spacing="1.4" fill="{INK}" font-family="{TYPE}">REVIEWER · plain code</text>'
                   f'<text x="14" y="60" font-size="11.5" fill="{INK}" font-family="{HAND}">{tl}</text></g>')
        out.append(_pin(500, 40))
    # the polaroid
    label, color = stamp_for(case)
    score = risk_score(case)
    out.append(_string(cx, 222, 500, 150, "#8a7d6a") if rv else "")
    out.append(f'<g transform="translate({cx - 100} {cy - 108}) rotate(-1.4 100 130)" filter="url(#shadow)"><rect width="200" height="262" fill="#fdfdf8"/>'
               f'<rect x="12" y="12" width="176" height="170" fill="#3b2d22"/><circle cx="100" cy="97" r="62" fill="#e8d9b4" stroke="{risk_color(score)}" stroke-width="7"/>'
               f'<text x="100" y="116" text-anchor="middle" font-size="52" font-weight="900" fill="{INK}" font-family="Georgia,serif">{esc(initials(case["vendor_name"] or case["subject"]))}</text>'
               f'<g transform="translate(166 30)"><circle r="19" fill="{risk_color(score)}"/><text y="5" text-anchor="middle" font-size="14" font-weight="900" fill="#fff" font-family="{TYPE}">{score}</text></g>'
               f'<text x="100" y="206" text-anchor="middle" font-size="15" fill="#1c3f8a" font-family="{HAND}">{esc(wrap(case["vendor_name"] or case["subject"], 22, 1)[0])}</text>'
               f'<text x="100" y="232" text-anchor="middle" font-size="10" fill="{GREY}" font-family="{TYPE}">{esc(case["case_id"])} · risk {score}/100</text>'
               f'<text x="100" y="248" text-anchor="middle" font-size="9" fill="{GREY}" font-family="{TYPE}">{esc(wrap(case["requester"], 30, 1)[0])}</text></g>')
    out.append(_pin(cx, 222))
    out.append(_stamp_svg(cx + 4, cy + 34, label, color, -12, 14 if len(label) < 12 else 12, None))
    if case.get("injection"):
        out.append(f'<g transform="translate(500 192) rotate(5)"><rect x="-122" y="-13" width="244" height="26" fill="{RED}" stroke="#fff" stroke-width="1.5"/>'
                   f'<text y="5" text-anchor="middle" font-size="12" font-weight="900" letter-spacing="1.5" fill="#fff" font-family="{TYPE}">⚠ THE EMAIL GAVE ORDERS</text></g>')
    # the verdict card (bottom centre)
    decision = (case.get("decision") or "no decision yet").upper()
    reasons = (case.get("reasons") or [""])[0]
    detail = "".join(f'<tspan x="14" dy="{0 if i == 0 else 15}">{esc(ln)}</tspan>' for i, ln in enumerate(wrap(reasons, 44, 3)))
    flags = "  ".join(f"⚑ {f.replace('_', ' ')}" for f in case.get("flags", [])[:3]) or "no flags raised"
    out.append(f'<g transform="translate(332 540) rotate(.8)" filter="url(#shadow)"><rect width="336" height="172" fill="{CARD}" stroke="#d9cdb0"/><rect width="336" height="24" fill="{INK}"/>'
               f'<text x="14" y="17" font-size="11" font-weight="900" letter-spacing="2" fill="#fff" font-family="{TYPE}">THE TEAM RECOMMENDS</text>'
               f'<text x="14" y="58" font-size="23" font-weight="900" fill="{color}" font-family="Georgia,serif">{esc(decision)}</text>'
               f'<text x="14" y="84" font-size="10.5" fill="{INK}" font-family="{TYPE}">{detail}</text>'
               f'<text x="14" y="150" font-size="10.5" fill="{RED}" font-family="{TYPE}">{esc(flags[:52])}</text>'
               f'<text x="14" y="166" font-size="9" fill="{GREY}" font-family="{TYPE}">a person decides; this is only a recommendation</text></g>')
    out.append(_pin(500, 544))
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------------------------------------- approval slip, receipt, letter, story
def slip(case: dict) -> str:
    need = case.get("approvers_required") or 1
    approvals = case.get("approvals", [])
    spend = case.get("annual_spend_gbp")
    boxes = ""
    for i in range(need):
        if i < len(approvals):
            a = approvals[i]
            boxes += (f'<div class="sig"><span class="who">{esc(a["approver"])}</span><span class="cap">signature {i + 1} · {esc(a["at"][:10])}</span></div>')
        else:
            boxes += f'<div class="sig empty"><span class="x">✕</span><span class="who">&nbsp;&nbsp;&nbsp;sign here</span><span class="cap">signature {i + 1} · a different person</span></div>'
    status = case["status"]
    if status == "CREATED":
        foot = f'<div style="margin-top:22px;text-align:center"><div class="wax">{esc(case.get("vendor_id"))}<br>FILED</div><div class="lock">filed in the vendor master, once, keyed by the case number</div></div>'
    elif status == "REJECTED":
        foot = '<div class="lock" style="margin-top:18px">⛔ closed by a person: the vendor master stays untouched</div>'
    else:
        foot = f'<div class="lock" style="margin-top:22px">🔒 the vendor master is locked until {"both signatures are" if need == 2 else "the signature is"} on this slip</div>'
    money = f"£{spend:,.0f} a year" if spend is not None else "spend not stated"
    return (f'<div class="slip"><div class="sh"><span>APPROVAL SLIP</span><span>FILE {esc(case["case_id"])}</span></div>'
            f'<div class="ln">Vendor: <b>{esc(case["vendor_name"] or case["subject"])}</b></div>'
            f'<div class="ln">Spend: <b>{money}</b> → <b>{need} signature{"s" if need == 2 else ""}</b>{" from two different people" if need == 2 else ""}</div>'
            f'{boxes}{foot}</div>')


def receipt(case: dict) -> str:
    rows = "".join(f'<div class="r"><span>{esc(role)}</span><span>{int(v["model_calls"])} calls · {int(v["tokens"]):,} tok</span></div>'
                   for role, v in case.get("per_role", {}).items())
    u = case["usage"]
    return (f'<div class="receipt"><div style="text-align:center;font-weight:900;letter-spacing:.2em">COST OF THIS FILE</div>{rows}'
            f'<div class="r" style="font-weight:900;border-bottom:2px solid {INK}"><span>TOTAL</span><span>{int(u["model_calls"])} calls · {int(u["tokens"]):,} tok</span></div>'
            f'<div class="r"><span>tool calls</span><span>{int(u["tool_calls"])}</span></div><div class="r"><span>time</span><span>{u["seconds"]:.0f} s</span></div></div>')


def letter(draft: dict | None) -> str:
    if not draft:
        return ""
    return (f'<div class="tiny" style="margin-bottom:6px">To: {esc(draft["to"])}<br>Subject: {esc(draft["subject"])}</div>'
            f'<div class="letter"><span class="rs" style="--c:{RED};position:absolute;right:10px;top:8px;font-size:.62rem;transform:rotate(6deg)">draft · not sent</span>{esc(draft["body"])}</div>')


STORY_ICON = {"request_received": "📨", "reply_received": "📬", "verdict": "⚖️", "decision": "🧭", "state_change": "🔀", "write": "🏦",
              "reminder": "⏰", "refused": "🚫", "draft": "✉️", "stopped": "🛑", "handoff_rejected": "🔁"}


def actor_color(who: str) -> str:
    if who in ("intake", "documents", "compliance", "finance", "followup"):
        return BLUE
    return {"reviewer": "#6a3d9a", "supervisor": RED, "system": GREY}.get(who, GREEN)


def story(entries: list[dict]) -> str:
    """The audit trail told as handwritten case notes: only the moments that matter, in plain words."""
    lines, handoffs = [], []
    for e in entries:
        ev, who, det = e["event"], e["who"], e["detail"]
        human = actor_color(who) == GREEN
        if ev == "handoff":
            handoffs.append(who)
            continue
        if ev == "tool_call":
            continue
        if handoffs:
            lines.append(("👷", f"{', '.join(handoffs)} each handed over a checked report"))
            handoffs = []
        icon = STORY_ICON.get(ev, "•")
        if ev == "verdict":
            text = ("The reviewer sent work back: " + det.split(": ", 1)[-1]) if det.startswith("revise") else "The reviewer checked every result against its evidence and approved."
            lines.append((icon, text))
        elif ev == "decision" and human:
            lines.append(("🖋️", f"{who}: {det}" + (f' (“{e["evidence"]}”)' if e["evidence"] else "")))
        elif ev == "decision":
            lines.append((icon, "The team recommended: " + det.replace("recommended: ", "")))
        elif ev == "state_change":
            lines.append((icon, det.replace("->", "→")))
        else:
            lines.append((icon, (f"{who}: " if human else "") + det))
    if handoffs:
        lines.append(("👷", f"{', '.join(handoffs)} each handed over a checked report"))
    rows = "".join(f"<div>{i} &nbsp;{esc(t)}</div>" for i, t in lines)
    return f'<div class="note" style="transform:rotate(.3deg);background:#fffbe0"><div class="story">{rows}</div></div>'


# ---------------------------------------------------------------------------------------------- the typewriter roll
def roll(entries: list[dict], flip: bool = False) -> str:
    rows = ""
    for i, e in enumerate(entries):
        evid = f'<span class="e">↳ {esc(e["evidence"])}</span>' if e["evidence"] else ""
        rows += (f'<div class="rl" style="--i:{i}"><span class="n">{e["seq"]:03d}</span><span class="t">{esc(e["at"][11:19])}</span>'
                 f'<span class="w" style="color:{actor_color(e["who"])}">[{esc(e["who"])}]</span>'
                 f'<span class="d{" f2" if flip else ""}"><b>{esc(e["event"])}</b> {esc(e["detail"])}{evid}</span>'
                 f'<span class="h">⛓ {esc(e["hash"][:6])}</span></div>')
    return f'<div class="roll">{rows}</div>'


# ---------------------------------------------------------------------------------------------- evaluation: the race
def _outcome(expected: str, got: str | None) -> tuple[str, str]:
    if got == expected:
        return GREEN, "right"
    if got == "stop for a person" and expected == "reject":
        return AMBER, "safe miss"
    return RED, "wrong"


def race_svg(res: dict) -> str:
    """Two cars run a track with one gate per test case; a gate's flag shows whether that agent got the case right. The cars'
    finishing times follow the measured seconds per case, so the slower design really does arrive later."""
    a, b = res["single"], res["team"]
    cases = res["per_case"]
    n = len(cases)
    x0, x1 = 120, 930
    t_a = 5.0
    t_b = max(t_a, t_a * b["seconds_per_case"] / a["seconds_per_case"]) if a["seconds_per_case"] and b["seconds_per_case"] else t_a
    if not (a["seconds_per_case"] and b["seconds_per_case"]):
        t_b = t_a * b["model_calls_per_case"] / a["model_calls_per_case"]
    lanes = [("single", "SINGLE AGENT", 100, "🏎️", t_a, a), ("team", "THE TEAM", 220, "🚐", t_b, b)]
    out = ['<svg viewBox="0 0 1000 330" width="100%"><defs><filter id="ds2"><feDropShadow dx="1" dy="2" stdDeviation="1.5" flood-opacity=".35"/></filter></defs>',
           '<rect width="1000" height="330" rx="6" fill="#3a3a3f"/>']
    for key, label, y, car, dur, stats in lanes:
        out.append(f'<rect x="20" y="{y - 40}" width="960" height="84" fill="#4a4a50"/><line x1="20" x2="980" y1="{y + 2}" y2="{y + 2}" stroke="#e8e0c8" stroke-width="2" stroke-dasharray="14 12" opacity=".5"/>')
        out.append(f'<text x="30" y="{y - 46}" font-size="11" font-weight="900" letter-spacing="2" fill="#f0e6c8" font-family="{TYPE}">{label} · {stats["seconds_per_case"]:.0f} s and {stats["model_calls_per_case"]} calls per case</text>')
        for i, c in enumerate(cases):
            gx = x0 + (i + 1) * (x1 - x0) / (n + 1)
            col, word = _outcome(c["expected"], c[key])
            out.append(f'<g filter="url(#ds2)"><rect x="{gx - 1.5:.0f}" y="{y - 30}" width="3" height="46" fill="#ddd"/><path d="M {gx + 1.5:.0f} {y - 30} l 16 6 l -16 6 z" fill="{col}"/></g>'
                       f'<text x="{gx:.0f}" y="{y + 34}" text-anchor="middle" font-size="7.5" fill="#cfc7ae" font-family="{TYPE}"><title>{esc(c["id"])}: {word}</title>{esc(c["id"][4:])}</text>')
        out.append(f'<text x="{x0 - 60}" y="{y + 12}" font-size="34">{car}'
                   f'<animateTransform attributeName="transform" type="translate" from="0 0" to="{x1 - x0 + 50} 0" dur="{dur:.1f}s" fill="freeze" '
                   f'calcMode="spline" keyTimes="0;1" keySplines=".35 .1 .45 1"/></text>')
        out.append(f'<text x="965" y="{y + 12}" text-anchor="end" font-size="26">🏁</text>')
    out.append("</svg>")
    return "".join(out)


def scoreboard(res: dict) -> str:
    a, b = res["single"], res["team"]

    def tiles(text, win):
        return "".join(f'<span class="flap{" win" if win else ""}">{esc(ch)}</span>' for ch in str(text))

    rows = [("DECISIONS RIGHT", f'{a["decisions_right"]}/{a["cases"]}', f'{b["decisions_right"]}/{b["cases"]}', a["decisions_right"], b["decisions_right"], True),
            ("UNSAFE MISSES", a["unsafe_misses"], b["unsafe_misses"], a["unsafe_misses"], b["unsafe_misses"], False),
            ("INJECTIONS HANDLED", f'{a["injection_handled"]}/{a["injection_cases"]}', f'{b["injection_handled"]}/{b["injection_cases"]}', a["injection_handled"], b["injection_handled"], True),
            ("MODEL CALLS / CASE", a["model_calls_per_case"], b["model_calls_per_case"], a["model_calls_per_case"], b["model_calls_per_case"], False),
            ("TOKENS / CASE", f'{a["tokens_per_case"]:,}', f'{b["tokens_per_case"]:,}', a["tokens_per_case"], b["tokens_per_case"], False),
            ("SECONDS / CASE", a["seconds_per_case"], b["seconds_per_case"], a["seconds_per_case"], b["seconds_per_case"], False),
            ("COST, ALL CASES ($)", f'{a["cost_usd"]:.3f}', f'{b["cost_usd"]:.3f}', a["cost_usd"], b["cost_usd"], False)]
    out = f'<div class="score tiny"><span></span><span>🏎️ single agent</span><span>🚐 the team</span></div>'
    for label, ta, tb, va, vb, higher in rows:
        wa = (va > vb) if higher else (va < vb)
        wb = (vb > va) if higher else (vb < va)
        out += f'<div class="score"><b>{label}</b><span>{tiles(ta, wa)}</span><span>{tiles(tb, wb)}</span></div>'
    return out


def history() -> str:
    return '<div class="hist">' + "".join(f'<div style="border-top:6px solid {c}"><b>{esc(t)}</b><br>{esc(a)}<br><span style="opacity:.7">{esc(b)}</span></div>'
                                          for t, a, b, c in LIVE_RUNS) + "</div>"


# ---------------------------------------------------------------------------------------------- rulebook: the marble run
_BINS = [("REJECT", RED, "§7.1"), ("STOP FOR A PERSON", "#c2571a", "§7.2"), ("WAITING FOR VENDOR", BLUE, "§7.3"), ("READY TO SIGN", GREEN, "§7.4")]
_RUNG_OF_FLAG = {"duplicate_vendor": 0, "watchlist_hit": 0, "possible_injection": 1, "possible_duplicate": 1, "watchlist_near_match": 1,
                 "bank_country_mismatch": 1, "bank_holder_mismatch": 1, "bank_account_shared": 1, "insurance_expired": 2, "payment_terms_over_limit": 2}


def marble_svg(sim: dict) -> str:
    """A marble drops through the four policy rules in order. The first rule whose condition is true tips the marble into its bin."""
    rung = sim["rung"]
    gy = [130, 240, 350]
    out = [f'<svg viewBox="0 0 640 540" width="100%"><defs><radialGradient id="mb" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#fff"/><stop offset=".3" stop-color="#e8554b"/>'
           f'<stop offset="1" stop-color="#5a0f0a"/></radialGradient><filter id="s3"><feDropShadow dx="2" dy="3" stdDeviation="2" flood-opacity=".35"/></filter></defs>',
           f'<rect width="640" height="540" rx="6" fill="#efe4c8" stroke="{INK}" stroke-width="3"/>',
           f'<path d="M 230 30 L 330 30 L 300 70 L 260 70 Z" fill="#b9a98a" stroke="{INK}" stroke-width="2"/>',
           f'<line x1="260" y1="70" x2="260" y2="500" stroke="{INK}" stroke-width="3"/><line x1="300" y1="70" x2="300" y2="500" stroke="{INK}" stroke-width="3"/>']
    for i, (label, col, sec) in enumerate(_BINS):
        y = gy[i] if i < 3 else 470
        out.append(f'<g filter="url(#s3)"><rect x="440" y="{y - 8 if i < 3 else y - 20}" width="180" height="{56 if i < 3 else 62}" rx="3" fill="{col}" opacity="{1 if i == rung else .28}"/></g>'
                   f'<text x="530" y="{(y + 14) if i < 3 else (y + 8)}" text-anchor="middle" font-size="12.5" font-weight="900" letter-spacing="1" fill="#fff" font-family="{TYPE}">{label}</text>'
                   f'<text x="530" y="{(y + 32) if i < 3 else (y + 28)}" text-anchor="middle" font-size="10" fill="#fff" font-family="{TYPE}">{sec}</text>')
    for i in range(3):
        y = gy[i]
        if i == rung:   # the rule that applies: a ramp that tips the marble out to its bin
            out.append(f'<path d="M 260 {y} L 440 {y + 22}" stroke="{INK}" stroke-width="6" stroke-linecap="round"/><text x="250" y="{y - 12}" text-anchor="end" font-size="11" font-weight="900" fill="{_BINS[i][1]}" font-family="{TYPE}">{_BINS[i][2]} ✔ applies</text>')
        else:           # a rule that does not apply: the flap hangs open and the marble falls past
            out.append(f'<line x1="260" y1="{y}" x2="260" y2="{y + 26}" stroke="#a89b7d" stroke-width="5" stroke-linecap="round"/>'
                       f'<text x="250" y="{y - 12}" text-anchor="end" font-size="10.5" fill="{GREY}" font-family="{TYPE}">{_BINS[i][2]} not met{" (outranked)" if i > rung else ""}</text>')
    lit = {}
    for f in sim["flags"]:
        lit.setdefault(_RUNG_OF_FLAG.get(f, 3), []).append(f.replace("_", " "))
    for i, names in lit.items():
        y = gy[i] if i < 3 else 470
        for j, nm in enumerate(names[:3]):
            out.append(f'<circle cx="24" cy="{y + 10 + j * 17}" r="5" fill="{RED}"><animate attributeName="opacity" values="1;.35;1" dur="1.4s" repeatCount="indefinite"/></circle>'
                       f'<text x="36" y="{y + 14 + j * 17}" font-size="9.5" fill="{INK}" font-family="{TYPE}">{esc(nm[:26])}</text>')
    path = f"M 280 40 L 280 {gy[rung] + 6} L 440 {gy[rung] + 34}" if rung < 3 else "M 280 40 L 280 480"
    out.append(f'<circle r="12" fill="url(#mb)" stroke="#3a0a06" stroke-width="1" filter="url(#s3)"><animateMotion path="{path}" dur="2.6s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines=".6 .0 .9 .6"/></circle>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------------------------------------- red team: the evidence bag
def redteam(text: str) -> tuple[str, list[str]]:
    """(HTML: the text in an evidence bag with the offending phrases circled in marker, names of the patterns that matched).
    Nothing is saved or sent."""
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
    return f'<div class="bag">{out}</div>', sorted(set(names))
