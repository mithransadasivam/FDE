"""What each option costs to run: unit economics from the price sheet (done, not a ticket)."""

import csv

from app.config import PRICE_FILE


def load_prices() -> dict[str, float]:
    with open(PRICE_FILE, newline="", encoding="utf-8") as f:
        return {r["item"]: float(r["value"]) for r in csv.DictReader(f)}


def cost_per_page_usd(cost: dict, p: dict[str, float]) -> dict[str, float]:
    """Variable cost of one page, split into model, OCR and public API."""
    parts = {"model": 0.0, "ocr": 0.0, "api": 0.0}
    if cost.get("public_api"):
        parts["api"] = p["public document api"]
        return parts
    m = cost["model"]
    model = (cost["input_tokens_per_page"] * p[f"{m} input"] + cost["output_tokens_per_page"] * p[f"{m} output"]) / 1e6
    if cost.get("regional"):
        model *= p["regional endpoint premium"]
    parts["model"] = model
    if cost.get("ocr"):
        parts["ocr"] = p["textract detect text"] / 1000
    return parts


def estimate(cost: dict, docs_per_month: float, pages_per_doc: float, p: dict[str, float]) -> dict:
    """Monthly run-cost in GBP, split into model, OCR, API and fixed platform costs."""
    fx = p["usd to gbp"]
    page = cost_per_page_usd(cost, p)
    pages = docs_per_month * pages_per_doc
    parts = {k: round(v * pages * fx, 2) for k, v in page.items()}
    parts["platform"] = round(cost["fixed_monthly_usd"] * fx, 2)
    total = round(sum(parts.values()), 2)
    return {"parts": parts, "total_gbp": total,
            "per_doc_gbp": round(total / docs_per_month, 4) if docs_per_month else 0.0}


def value_per_month(docs_per_month: float, minutes_saved_per_doc: float, p: dict[str, float]) -> float:
    return round(docs_per_month * minutes_saved_per_doc * p["analyst cost"], 2)
