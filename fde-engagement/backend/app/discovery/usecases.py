"""Use-case candidates and how they are ranked: value and feasibility up, risk down."""

import csv

from app.config import USE_CASES_FILE
from app.discovery.models import UseCase

WEIGHTS = {"value": 0.45, "feasibility": 0.35, "risk": 0.20}


def load_candidates() -> list[UseCase]:
    with open(USE_CASES_FILE, newline="", encoding="utf-8") as f:
        return [UseCase(**row) for row in csv.DictReader(f)]


def score_use_case(u: UseCase) -> float:
    """0-100. Excluded use cases score 0: a rule, not a weight, keeps them out."""
    if u.excluded_reason:
        return 0.0
    raw = WEIGHTS["value"] * u.value + WEIGHTS["feasibility"] * u.feasibility + WEIGHTS["risk"] * (6 - u.risk)
    return round((raw - 1) / 4 * 100, 1)
