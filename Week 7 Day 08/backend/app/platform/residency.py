"""Where does a Bedrock model call actually run? (done, not a ticket)

On Bedrock, the model ID decides the routing, not only the Region you call:

    anthropic.claude-sonnet-5        in-Region: processed in the Region you call (eu-west-2 = London)
    eu.anthropic.claude-haiku-5-5    geographic: may be processed in any of 7 EU Regions
    global.anthropic.claude-...      global: may be processed in any commercial Region

Helen's rule from Day 1 is "customer data stays in the UK", so the pilot needs an in-Region model in eu-west-2.
"""

import csv

from app.config import BEDROCK_MODELS_FILE

GEO_PREFIXES = {"eu": "the EU", "us": "the US", "apac": "Asia Pacific", "au": "Australia", "jp": "Japan", "ca": "Canada", "in": "India"}
EU_ROUTES = ["eu-central-1 (Frankfurt)", "eu-north-1 (Stockholm)", "eu-south-1 (Milan)", "eu-south-2 (Spain)",
             "eu-west-1 (Ireland)", "eu-west-2 (London)", "eu-west-3 (Paris)"]
UK_REGION = "eu-west-2"


def routing(model_id: str) -> str:
    """'in-region', 'geo' or 'global', from the model ID's prefix."""
    head = model_id.split(".", 1)[0]
    if head == "global":
        return "global"
    if head in GEO_PREFIXES:
        return "geo"
    return "in-region"


def models() -> list[dict]:
    with open(BEDROCK_MODELS_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def model_for(model_id: str) -> dict | None:
    bare = model_id.split(".", 1)[1] if routing(model_id) != "in-region" else model_id
    return next((m for m in models() if m["in_region_model_id"] == bare), None)


def residency(model_id: str, region: str) -> dict:
    """Does a call to this model ID from this Region keep the customer's data in the UK?"""
    r = routing(model_id)
    m = model_for(model_id)
    if region != UK_REGION:
        where, ok = f"the {region} Region, outside the UK", False
    elif r == "global":
        where, ok = "any commercial AWS Region in the world", False
    elif r == "geo":
        geo = GEO_PREFIXES[model_id.split(".", 1)[0]]
        where, ok = f"any Region in {geo}" + (f": {', '.join(EU_ROUTES)}" if geo == "the EU" else ""), False
    elif m is not None and m["london_in_region"] != "yes":
        where, ok = "nowhere: London does not serve this model in-Region, so the call fails", False
    else:
        where, ok = "London (eu-west-2) only", True
    return {"model_id": model_id, "region": region, "routing": r, "processed_in": where, "stays_in_uk": ok,
            "model": m["model"] if m else "", "fix": "" if ok else uk_alternatives()}


def uk_alternatives() -> str:
    names = [f"{m['model']} ({m['in_region_model_id']})" for m in models() if m["london_in_region"] == "yes"]
    return "Models served in-Region in London: " + ", ".join(names)


def cost_per_document(model_id: str, input_tokens: float, output_tokens: float) -> float | None:
    """USD for one document at the model's Bedrock price, or None if the price is not in the file."""
    m = model_for(model_id)
    if not m or not m["input_usd_per_m"]:
        return None
    return (input_tokens * float(m["input_usd_per_m"]) + output_tokens * float(m["output_usd_per_m"])) / 1e6
