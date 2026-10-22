"""Activity 4: check_notice() finds visible problems in a notice. Run: pytest tests/test_check_notice.py"""

from app.notice_checks import check_notice
from tests.day14_fakes import NOTICE

MUST = ["Finance Portal", "07:58", "status page"]


def test_a_good_notice_has_no_problems():
    assert check_notice(NOTICE, MUST) == []


def test_missing_terms_are_listed_in_order_ignoring_case():
    notice = {
        **NOTICE,
        "title": "Portal unavailable",
        "body": "The FINANCE PORTAL is down. See the status page.",
    }
    assert check_notice(notice, ["finance portal", "07:58", "10:00"])[:2] == [
        "missing: 07:58",
        "missing: 10:00",
    ]
    assert (
        check_notice(
            {**NOTICE, "body": "Down.", "actions": ["Check the status page"]},
            ["status page"],
        )
        == []
    )


def test_too_long():
    notice = {**NOTICE, "body": "word " * 181}
    assert "too long: 181 words (limit 180)" in check_notice(notice, [])
    assert check_notice({**NOTICE, "body": "word " * 180}, []) == []


def test_no_actions_and_no_sources():
    notice = {k: v for k, v in NOTICE.items() if k not in ("actions", "sources")}
    assert check_notice(notice, []) == ["no action for staff", "no sources"]
    assert check_notice({**NOTICE, "actions": [], "sources": []}, []) == [
        "no action for staff",
        "no sources",
    ]


def test_names_of_people_are_flagged_once_each():
    notice = {
        **NOTICE,
        "body": "q.tan and w.fischer reported it; q.tan first. See e.g. the status page.",
        "actions": ["Ask a.mensah"],
    }
    assert check_notice(notice, ["status page"]) == [
        "names a person: q.tan",
        "names a person: w.fischer",
        "names a person: a.mensah",
    ]
