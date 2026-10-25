"""Phase 4: the load test is reproducible. Two runs with the same seed ask the same questions in the same order."""
import csv
from collections import Counter
from pathlib import Path

from scripts.loadtest import draw_questions
from tower.metrics import percentile

ROOT = Path(__file__).resolve().parent.parent


def test_same_seed_same_questions_in_the_same_order():
    assert draw_questions(60, 17) == draw_questions(60, 17)
    assert draw_questions(60, 17) != draw_questions(60, 18)
    assert len(draw_questions(60, 17)) == 60


def test_questions_are_drawn_by_weight():
    rows = list(csv.DictReader(open(ROOT / "data" / "operator_questions.csv", encoding="utf-8")))
    w = {r["question"]: int(r["weight"]) for r in rows}
    drawn = Counter(draw_questions(6000, 1))
    heavy = max(w, key=w.get)
    light = min(w, key=w.get)
    assert drawn[heavy] > drawn[light] * 2
    assert set(drawn) <= set(w)


def test_percentiles():
    assert percentile([1, 2, 3, 4, 5], 50) == 3
    assert round(percentile(list(range(1, 101)), 95), 2) == 95.05
    assert percentile([], 95) == 0.0
