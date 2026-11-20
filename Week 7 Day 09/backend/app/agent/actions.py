"""The operations agent's tools (done, not a ticket).

Bank tools reach the CRM, KYC exceptions and the document store through the MCP server's own tools (Day 8), as the
person: each call exchanges the person's token (ENG-802), so every system applies its rules and its audit names them.
Screen tools work CaseFlow Classic through LegacyScreen. The agent signs in there with a token for "caseflow",
from the same exchange: it never sees a password.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from app.agent import screen as scr
from app.agent.models import Run, ScreenError
from app.integration import tools as bank
from app.integration.downstream import downstream_token
from app.integration.models import Identity, ToolRefused

BANK_TOOLS = {"get_exception": ("kyc-exceptions", "ticket_id"), "get_customer": ("crm", "customer_id"),
              "list_documents": ("documents", "customer_id"), "comment_on_exception": ("kyc-exceptions", "ticket_id")}
SCREEN_TOOLS = {"open_caseflow", "look", "click", "type", "choose"}
TOOLS_DOC = """get_exception(ticket_id)                 one KYC exception (KX-…): its kind, case and customer
get_customer(customer_id)                one customer from the CRM (CU-…): risk rating, contacts, notes
list_documents(customer_id)              the documents on the customer's file
comment_on_exception(ticket_id, text)    add a comment to the exception, in the person's name
open_caseflow()                          sign in to CaseFlow Classic as the person; shows the main menu
look()                                   read the current CaseFlow screen again
click(name, role?)                       press the button or link with this name (role: button or link)
type(field, text)                        type into the text box with this label
choose(field, option)                    pick an option in the list with this label
finish(result, summary)                  end the run. result: recorded (an outcome was recorded) or handed_back"""


@dataclass
class RunContext:
    identity: Identity
    legacy_url: str
    shots_dir: Path
    run: Run
    screen: scr.LegacyScreen | None = None
    elements: list = field(default_factory=list)
    title: str = ""
    chosen: dict = field(default_factory=dict)       # what the agent picked on the outcome form: Outcome, Reason code, Note
    facts: dict = field(default_factory=dict)        # what the agent has read (the scripted model uses it)

    def close(self):
        if self.screen:
            self.screen.close()


def _short(data) -> str:
    text = json.dumps(data, ensure_ascii=False)
    return text if len(text) < 2500 else text[:2500] + "…"


def _resolve(ctx: RunContext, tool: str, args: dict) -> dict | None:
    """The control a screen action would use (ENG-901's find_element). A click tries a button, then a link."""
    if tool == "click":
        roles = [args["role"]] if args.get("role") else ["button", "link"]
        errors = []
        for role in roles:
            try:
                return scr.find_element(ctx.elements, role, args.get("name", ""))
            except ScreenError as e:
                errors.append(str(e))
        raise ScreenError(errors[-1])
    if tool == "type":
        return scr.find_element(ctx.elements, "textbox", args.get("field", ""))
    if tool == "choose":
        return scr.find_element(ctx.elements, "combobox", args.get("field", ""))
    return None


def plan(ctx: RunContext, tool: str, args: dict) -> tuple[dict, dict | None]:
    """What the gate sees (system, tool, target, fingerprint) and the control the action would use.
    The target of a click is the control it would really press, as found on the screen now."""
    if tool in BANK_TOOLS:
        system, key = BANK_TOOLS[tool]
        target = str(args.get(key, ""))
        return {"system": system, "tool": tool, "target": target, "args": args,
                "fingerprint": f"{system}|{tool}|{target}|{json.dumps(args, sort_keys=True)}"}, None
    if tool not in SCREEN_TOOLS:
        raise ScreenError(f"There is no tool called {tool}")
    if tool in ("open_caseflow", "look"):
        return {"system": "caseflow", "tool": tool, "target": "*", "args": args, "fingerprint": f"caseflow|{tool}"}, None
    if ctx.screen is None:
        raise ScreenError("CaseFlow Classic is not open: call open_caseflow() first")
    el = _resolve(ctx, tool, args)
    target = el["name"]
    fp = f"caseflow|{tool}|{ctx.title}|{target}|{json.dumps(args, sort_keys=True)}"
    if tool == "click":
        rows = [e["name"] for e in ctx.elements if e["role"] == "row"]
        fp = f"caseflow|click|{ctx.title}|{target}|" + hashlib.sha256("\n".join(rows).encode()).hexdigest()[:16]
    return {"system": "caseflow", "tool": tool, "target": target, "args": args, "fingerprint": fp}, el


def confirm_rows(ctx: RunContext) -> list[list[str]]:
    """The rows of the screen as [label, value]: what a person approves."""
    return [r["name"].split(" | ", 1) for r in ctx.elements if r["role"] == "row" and " | " in r["name"]]


def _screen_obs(ctx: RunContext) -> str:
    ctx.title = ctx.screen.title()
    return scr.snapshot_text(ctx.title, ctx.elements)


def execute(ctx: RunContext, tool: str, args: dict, el: dict | None) -> str:
    """Do one action and return what the agent observes."""
    if tool in BANK_TOOLS:
        try:
            fn = getattr(bank, tool)
            data = fn(ctx.identity, **{k: v for k, v in args.items() if k in fn.__code__.co_varnames})
        except ToolRefused as e:
            return f"Refused by the bank: {e}"
        except TypeError as e:
            return f"Wrong arguments for {tool}: {e}"
        ctx.facts[tool] = data
        return _short(data)
    if tool == "open_caseflow":
        if ctx.screen is None:
            ctx.screen = scr.LegacyScreen(ctx.legacy_url)
            token = downstream_token(ctx.identity, "caseflow", bank.bank_http())
            ctx.elements = ctx.screen.start(token)
        return _screen_obs(ctx)
    if tool == "look":
        ctx.elements = ctx.screen.read()
        return _screen_obs(ctx)
    if tool == "click":
        ctx.elements = ctx.screen.act(el, "click")
        obs = _screen_obs(ctx)
        if el["name"] == "Confirm" or ctx.title.startswith(("Outcome recorded", "Case withdrawn")):
            try:
                ref = scr.check_saved(ctx.elements, ctx.chosen.get("Outcome", ""))
                ctx.run.reference = ref
                ctx.run.outcome = ctx.chosen.get("Outcome", "")
                ctx.run.reason_code = ctx.chosen.get("Reason code", "")[:3]
                obs += f"\nCaseFlow saved it: reference {ref}"
            except ScreenError as e:
                ctx.facts["check_failed"] = str(e)
                obs += f"\nCHECK FAILED: {e}"
        return obs
    if tool == "type":
        ctx.elements = ctx.screen.act(el, "type", str(args.get("text", "")))
        ctx.chosen[el["name"]] = str(args.get("text", ""))
        return _screen_obs(ctx)
    if tool == "choose":
        ctx.elements = ctx.screen.act(el, "choose", str(args.get("option", "")))
        ctx.chosen[el["name"]] = str(args.get("option", ""))
        return _screen_obs(ctx)
    raise ScreenError(f"There is no tool called {tool}")
