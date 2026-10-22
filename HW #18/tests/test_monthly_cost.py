"""Day 16, homework Task 1: monthly_cost() turns a load test's cost per 1,000 into a monthly bill."""

import pytest

from app.perf import monthly_cost


def test_ten_thousand_questions_a_day_for_thirty_days():
    assert monthly_cost(3.50) == 1050.0  # 3.50 per 1,000 x 10 x 30


def test_other_volumes_and_months():
    assert monthly_cost(3.50, queries_per_day=2_000, days=31) == 217.0


def test_rounded_to_cents():
    assert monthly_cost(0.1234) == 37.02


def test_negative_numbers_are_refused():
    with pytest.raises(ValueError):
        monthly_cost(-1)
    with pytest.raises(ValueError):
        monthly_cost(1, queries_per_day=-5)
