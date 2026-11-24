"""Tell the right team in Slack about a new KYC exception (done, not a ticket).

The message uses Slack's incoming-webhook format (text plus Block Kit blocks), so the same payload works on the bank's
Slack stand-in and on a real Slack workspace (FDE_SLACK_WEBHOOK_URL, the stretch exercise).
"""

import httpx

from app.config import BANK_URL, SLACK_WEBHOOK_URL

CHANNEL_FOR_REGION = {"N": "kyc-north", "M": "kyc-midlands", "S": "kyc-south"}
TEAM_NAMES = {"N1": "North 1", "N2": "North 2", "M1": "Midlands 1", "M2": "Midlands 2", "S1": "South 1", "S2": "South 2"}


def channels_for(ticket: dict) -> list[str]:
    out = [CHANNEL_FOR_REGION[ticket["team_id"][0]]]
    if ticket.get("kind") == "escalation":
        out.append("financial-crime")
    return out


def message(ticket: dict) -> dict:
    team = TEAM_NAMES.get(ticket["team_id"], ticket["team_id"])
    text = f"New KYC exception {ticket['ticket_id']} ({team}): {ticket['title']}"
    return {"text": text, "blocks": [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*New KYC exception {ticket['ticket_id']}*\n{ticket['title']}"}},
        {"type": "section", "fields": [{"type": "mrkdwn", "text": f"*Team*\n{team}"}, {"type": "mrkdwn", "text": f"*Kind*\n{ticket['kind'].replace('_', ' ')}"},
                                       {"type": "mrkdwn", "text": f"*Case*\n{ticket['case_id']}"}, {"type": "mrkdwn", "text": f"*Status*\n{ticket['status']}"}]},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": "From the KYC exceptions system · signature checked · no customer name in Slack"}]},
    ]}


def post(ticket: dict, http: httpx.Client | None = None) -> list[dict]:
    h = http or httpx.Client(timeout=10)
    out = []
    payload = message(ticket)
    for ch in channels_for(ticket):
        r = h.post(f"{BANK_URL}/slack/hooks/{ch}", json=payload)
        out.append({"channel": ch, "status": r.status_code})
    if SLACK_WEBHOOK_URL:
        try:
            r = h.post(SLACK_WEBHOOK_URL, json=payload)
            out.append({"channel": "real Slack", "status": r.status_code})
        except httpx.HTTPError as e:
            out.append({"channel": "real Slack", "status": 0, "error": str(e)})
    return out
