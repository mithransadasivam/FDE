"""Ticket ENG-903: the gate between the agent and the bank's systems of record.

Every action the agent wants to take is looked up in the bank's risk table (data/Day09_Slide21_action_risks.csv).
Reading is allowed; a write to a system of record needs a person's approval of exactly that write; some actions are never allowed.
"""

from app.agent.models import Decision

APPROVAL_LIFETIME_S = 900  # an approval is good for 15 minutes


def gate(action: dict, rules: list[dict], approvals: list[dict], now: float) -> Decision:
    """allow, ask or deny for one action.

    action     "system", "tool", "target" and "fingerprint" (what exactly would be written)
    rules      rows of the risk table: "system", "tool", "target" (a name, or * for any), "tier" and "why"
    approvals  this run's approvals so far: "fingerprint", "status", "decided_by", "note", "decided_at"

    1. Find the rule: same system and tool, and the same target; if there is none, the row whose target is *.
       No rule at all                      -> deny  "Not in the risk table: caseflow click Print"
    2. tier read or log                    -> allow, with the rule's why
    3. tier deny                           -> deny, with the rule's why
    4. tier approve: the latest approval with the same fingerprint decides
         approved, decided less than APPROVAL_LIFETIME_S ago  -> allow "Approved by tom.reyes"
         approved, but older                                  -> ask   "The approval has expired: ask again"
         rejected                                             -> deny  "Rejected by tom.reyes: <note>"
         none, or still pending                               -> ask   "Needs a person's approval: <why>"
    """
    same = [r for r in rules if r["system"] == action["system"] and r["tool"] == action["tool"]]
    rule = next((r for r in same if r["target"] == action["target"]), None) or next((r for r in same if r["target"] == "*"), None)
    if rule is None:
        return Decision(kind="deny", reason=f"Not in the risk table: {action['system']} {action['tool']} {action['target']}")
    if rule["tier"] in ("read", "log"):
        return Decision(kind="allow", reason=rule["why"])
    if rule["tier"] == "deny":
        return Decision(kind="deny", reason=rule["why"])
    # tier approve: the latest approval of exactly this write decides
    mine = [a for a in approvals if a["fingerprint"] == action["fingerprint"]]
    last = mine[-1] if mine else None
    if last and last["status"] == "approved":
        if now - last["decided_at"] < APPROVAL_LIFETIME_S:
            return Decision(kind="allow", reason=f"Approved by {last['decided_by']}")
        return Decision(kind="ask", reason="The approval has expired: ask again")
    if last and last["status"] == "rejected":
        return Decision(kind="deny", reason=f"Rejected by {last['decided_by']}: {last['note']}")
    return Decision(kind="ask", reason=f"Needs a person's approval: {rule['why']}")
