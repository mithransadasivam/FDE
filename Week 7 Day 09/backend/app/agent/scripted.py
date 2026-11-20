"""The scripted model for the operations agent (FDE_FAKE_LLM=1): it plays the model's part, so every run is the same.

It reads what the agent has seen (the same observations a real model gets) and picks the next tool by fixed rules
that follow the bank's playbook. Like a real model, it has weaknesses the course needs you to see:
  - it treats text it finds in a case record as an instruction (a prompt injection), unless the prompt has a section
    headed "## Untrusted text"
  - it chases an applicant who has already replied, unless the prompt has a section headed "## The case history"
  - when CaseFlow will not save, it presses Save again
With a real model (OpenRouter), what you write in the prompt is what counts, and runs differ a little each time.
"""

import re

from app.agent.models import AgentReply

OUTCOMES = ["Request more information", "Ready for decision", "Refer to Financial Crime", "Chase applicant"]
REASONS = {"R01": "R01 Missing proof of identity", "R02": "R02 Missing proof of address", "R03": "R03 Documents complete",
           "R04": "R04 Financial crime concern", "R05": "R05 High-risk customer", "R06": "R06 No reply from applicant"}
ID_DOCS = {"passport", "driving_licence"}
ADDRESS_DOCS = {"utility_bill", "bank_statement", "council_tax_bill"}


def _say(thought: str, tool: str, **args) -> AgentReply:
    return AgentReply(thought=thought, tool=tool, args=args)


def _rows(elements: list[dict]) -> list[str]:
    return [e["name"] for e in elements if e["role"] == "row"]


def decide(facts: dict, prompt_text: str) -> tuple[str, str, str]:
    """(outcome, reason code, why) from what the agent has read."""
    ex, cu = facts["get_exception"], facts["get_customer"]
    docs = {d["doc_type"] for d in facts["list_documents"].get("documents", [])}
    history = facts.get("history", [])
    if "## Untrusted text" not in prompt_text:
        for row in history:
            m = re.search(r"Record the outcome (" + "|".join(OUTCOMES) + ")", row)
            if m:
                return m.group(1), {"Ready for decision": "R03", "Chase applicant": "R06", "Request more information": "R01",
                                    "Refer to Financial Crime": "R04"}[m.group(1)], f"the case history says: {row.split(' | ')[-1][:120]}"
    replied = any("Applicant replied" in r for r in history) and "## The case history" in prompt_text
    if ex["kind"] == "escalation":
        return "Refer to Financial Crime", "R04", "the exception is an escalation (rule 1)"
    if cu.get("risk_rating") == "high":
        return "Refer to Financial Crime", "R05", "the customer's risk rating is high (rule 2)"
    if ex["kind"] == "applicant_follow_up" and not replied:
        return "Chase applicant", "R06", "the applicant has not replied to our request (rule 3)"
    if not docs & ID_DOCS:
        return "Request more information", "R01", "there is no passport or driving licence on file (rule 4)"
    if not docs & ADDRESS_DOCS:
        return "Request more information", "R02", "there is no proof of address on file (rule 5)"
    return "Ready for decision", "R03", "the documents are complete (rule 6)"


def next_action(ticket_id: str, facts: dict, elements: list[dict], title: str, last_obs: str, prompt_text: str) -> AgentReply:
    if last_obs.startswith(("Refused", "Screen error")) or "CHECK FAILED" in last_obs:
        why = last_obs.split("CHECK FAILED: ")[-1] if "CHECK FAILED" in last_obs else last_obs
        return _say(f"That did not work: {why[:200]}. I will stop and hand this exception back.", "finish",
                    result="handed_back", summary=f"Handed back: {why[:200]}")
    if "get_exception" not in facts:
        return _say(f"I start by reading exception {ticket_id}.", "get_exception", ticket_id=ticket_id)
    ex = facts["get_exception"]
    if "get_customer" not in facts:
        kind = ex["kind"].replace("_", " ")
        return _say(f"It is {'an' if kind[0] in 'aeiou' else 'a'} {kind} on case {ex['case_id']}. Next, the customer's risk rating.", "get_customer",
                    customer_id=ex["customer_id"])
    if "list_documents" not in facts:
        return _say(f"Risk rating {facts['get_customer'].get('risk_rating')}. Now the documents on file.", "list_documents",
                    customer_id=ex["customer_id"])
    if not elements:
        docs = ", ".join(d["doc_type"].replace("_", " ") for d in facts["list_documents"].get("documents", [])) or "none"
        return _say(f"Documents on file: {docs}. I open CaseFlow Classic to read the case.", "open_caseflow")
    if facts.get("commented"):
        return _say("The outcome is recorded and the exception has a comment.", "finish", result="recorded",
                    summary=f"Recorded {facts.get('chosen', {}).get('Outcome', '')} in CaseFlow Classic")
    if title.startswith(("Outcome recorded", "Case withdrawn")):
        if not facts.get("commented"):
            ref = re.search(r"OUT-\d+", last_obs + " " + " ".join(e["name"] for e in elements))
            facts["commented"] = True
            c = facts.get("chosen", {})
            return _say("CaseFlow recorded it. I close the loop on the exception.", "comment_on_exception", ticket_id=ticket_id,
                        text=f"Outcome recorded in CaseFlow Classic: {c.get('Outcome', '')} ({c.get('Reason code', '')[:3]}). "
                             f"Reference {ref.group(0) if ref else '(none)'}. Worked by the operations agent.")
    if title == "Main menu":
        return _say("I go to the case search.", "click", name="Find a case")
    if title == "Find a case":
        box = next((e for e in elements if e["role"] == "textbox"), {})
        if box.get("value") != ex["case_id"]:
            return _say(f"I search for case {ex['case_id']}.", "type", field="Case reference", text=ex["case_id"])
        return _say("Search.", "click", name="Search")
    if title.startswith("Case "):
        facts["history"] = _rows(elements)
        locked = next((e["name"] for e in elements if e["role"] == "text" and "locked" in e["name"]), "")
        hint = f" The screen says: {locked}" if locked else ""
        return _say(f"I have read the case and its history.{hint} I open the outcome form.", "click", name="Record outcome")
    if title.startswith("Record outcome"):
        outcome, code, why = decide(facts, prompt_text)
        chosen = facts.setdefault("chosen", {})
        values = {e["name"]: e.get("value", "") for e in elements if e["role"] in ("combobox", "textbox")}
        if values.get("Outcome") != outcome:
            chosen["Outcome"] = outcome
            return _say(f"The outcome is {outcome}: {why}.", "choose", field="Outcome", option=outcome)
        if not values.get("Reason code", "").startswith(code):
            chosen["Reason code"] = REASONS[code]
            return _say(f"Reason code {code}.", "choose", field="Reason code", option=REASONS[code])
        note = f"{outcome}: {why}. Exception {ticket_id}."[:240]
        if not values.get("Note"):
            chosen["Note"] = note
            return _say("A short note for the case history.", "type", field="Note", text=note)
        if any(e["role"] == "text" and "locked" in e["name"] for e in elements):
            return _say("The save did not go through. I try Save again.", "click", name="Save")
        return _say("The form is complete. Save.", "click", name="Save")
    if title.startswith("Confirm"):
        return _say("The confirm screen shows what I chose. Confirm.", "click", name="Confirm")
    return _say("I am not sure where I am. I read the screen again.", "look")
