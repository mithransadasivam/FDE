"""Guardrail policies, and a scripted guardrail that imitates Amazon Bedrock Guardrails offline (done, not a ticket).

A policy is one JSON file in infra/guardrails/. Terraform builds the real guardrail from the same file
(infra/guardrail.tf), so the policy you test here is the policy you deploy.

The scripted guardrail is a teaching stand-in, not Bedrock: it uses simple patterns where Bedrock uses
trained models. It is good enough to show what each policy does to UC1. Run the probes on the real
guardrail too (python -m scripts.probe_guardrail with FDE_LLM_PROVIDER=bedrock): real results can differ.
"""

import json
import re

from app.config import GUARDRAILS_DIR
from app.llm import GuardrailBlocked

INJECTION = re.compile(
    r"ignore (all |any )?(the )?(previous|prior|earlier|above) instructions|disregard (your|the|all) (rules|instructions)"
    r"|system (note|override|prompt) to (the )?(ai|assistant|model)|you are now|ignore your rules",
    re.I,
)
DECISION = re.compile(r"\b(approved?|reject(ed)?|passes kyc|fails kyc)\b", re.I)
PATTERNS = {
    "EMAIL": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "PHONE": re.compile(r"(?:\+44\s?|\b0)\d{2,4}[\s-]?\d{3,4}[\s-]?\d{3,4}\b"),
    "CREDIT_DEBIT_CARD_NUMBER": re.compile(r"\b(?:\d[ -]?){15}\d\b"),
    "UK_NATIONAL_INSURANCE_NUMBER": re.compile(r"\b[A-CEGHJ-PR-TW-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b"),
}
FIELD_FOR = {"NAME": "full_name", "ADDRESS": "address"}  # what Bedrock's NAME and ADDRESS detectors would find in UC1's reply


def list_policies() -> list[str]:
    return sorted(p.stem for p in GUARDRAILS_DIR.glob("*.json"))


def load_policy(name: str) -> dict:
    p = GUARDRAILS_DIR / f"{name}.json"
    if not p.exists():
        raise FileNotFoundError(f"No guardrail policy infra/guardrails/{name}.json")
    return json.loads(p.read_text(encoding="utf-8"))


def summary(policy: dict) -> dict:
    """What a policy does, in words, for the Guardrails tab."""
    pa = next((f for f in policy["content_filters"] if f["type"] == "PROMPT_ATTACK"), None)
    return {
        "name": policy["name"], "description": policy["description"],
        "content_filters": [f"{f['type'].lower().replace('_', ' ')} ({f['input_strength'].lower()} in, {f['output_strength'].lower()} out)"
                            for f in policy["content_filters"]],
        "prompt_attack": bool(pa and pa["input_strength"] != "NONE"),
        "denied_topics": [t["name"] for t in policy["denied_topics"]],
        "masked": [e["type"] for e in policy["pii_entities"] if "ANONYMIZE" in (e["input_action"], e["output_action"])]
                  + [r["name"] for r in policy["regexes"] if r["output_action"] == "ANONYMIZE"],
        "blocked": [e["type"] for e in policy["pii_entities"] if "BLOCK" in (e["input_action"], e["output_action"])]
                   + [r["name"] for r in policy["regexes"] if r["output_action"] == "BLOCK"],
    }


def _mask(text: str, policy: dict, side: str) -> str:
    for e in policy["pii_entities"]:
        if e[f"{side}_action"] == "ANONYMIZE" and e["type"] in PATTERNS:
            text = PATTERNS[e["type"]].sub("{" + e["type"] + "}", text)
    for r in policy["regexes"]:
        if r[f"{side}_action"] == "ANONYMIZE":
            text = re.sub(r["pattern"], "{" + r["name"] + "}", text)
    return text


def _blocks(text: str, policy: dict, side: str) -> bool:
    for e in policy["pii_entities"]:
        if e[f"{side}_action"] == "BLOCK" and e["type"] in PATTERNS and PATTERNS[e["type"]].search(text):
            return True
    return any(r[f"{side}_action"] == "BLOCK" and re.search(r["pattern"], text) for r in policy["regexes"])


def scripted_guardrail(policy: dict, request: str, reply: str) -> str:
    """Apply a policy to one request (the OCR text sent to the model) and its JSON reply, as Bedrock would.

    Request side: a prompt attack (with the PROMPT_ATTACK filter on) blocks the call, as does a BLOCK entity.
    Reply side: the denied topic and BLOCK entities withhold the reply; ANONYMIZE entities are replaced by
    {TYPE}. NAME and ADDRESS cannot be found with a pattern, so they mask the full_name and address fields.
    """
    words = [ln.split(" | ", 1)[1] for ln in request.splitlines() if " | " in ln]
    request = " ".join(words) if words else request  # the OCR words, one per line as "id | text", read as running text
    pa = next((f for f in policy["content_filters"] if f["type"] == "PROMPT_ATTACK"), None)
    if pa and pa["input_strength"] != "NONE" and INJECTION.search(request):
        raise GuardrailBlocked("request", policy["blocked_input_messaging"])
    if _blocks(request, policy, "input"):
        raise GuardrailBlocked("request", policy["blocked_input_messaging"])

    data = json.loads(reply)
    masked_fields = {FIELD_FOR[e["type"]] for e in policy["pii_entities"]
                     if e["type"] in FIELD_FOR and "ANONYMIZE" in (e["input_action"], e["output_action"])}
    for f in data.get("fields", []):
        if f["name"] in masked_fields and f.get("value"):
            f["value"] = "{" + next(k for k, v in FIELD_FOR.items() if v == f["name"]) + "}"
        elif f.get("value"):
            f["value"] = _mask(f["value"], policy, "output")
        if policy["denied_topics"] and f["name"] == "decision":
            raise GuardrailBlocked("reply", policy["blocked_outputs_messaging"])
        if _blocks(f.get("value", ""), policy, "output"):
            raise GuardrailBlocked("reply", policy["blocked_outputs_messaging"])
    if policy["denied_topics"] and any(DECISION.search(f.get("value", "")) for f in data.get("fields", [])):
        raise GuardrailBlocked("reply", policy["blocked_outputs_messaging"])
    return json.dumps(data)
