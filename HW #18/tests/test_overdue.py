"""Day 18 homework, Task 1: overdue() lists the risks nobody has reviewed in time."""

from datetime import date

from app.risk_register import overdue

TODAY = date(2026, 11, 1)


def test_past_review_dates_are_overdue_in_register_order():
    rs = [
        {"id": "R01", "status": "open", "review_by": "2026-10-31"},
        {"id": "R02", "status": "open", "review_by": "2026-11-01"},
        {"id": "R03", "status": "accepted", "review_by": "2026-01-15"},
    ]
    assert overdue(rs, TODAY) == ["R01", "R03"]


def test_mitigated_risks_are_not_chased():
    assert (
        overdue(
            [{"id": "R01", "status": "mitigated", "review_by": "2026-01-01"}], TODAY
        )
        == []
    )


def test_no_review_date_means_overdue():
    assert overdue([{"id": "R09", "status": "open"}], TODAY) == ["R09"]


def test_today_defaults_to_the_real_date():
    assert overdue([{"id": "R01", "status": "open", "review_by": "2999-12-31"}]) == []
