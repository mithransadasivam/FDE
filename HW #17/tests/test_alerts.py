"""Day 15, homework Task 1: check_alerts() says which alert rules the dashboard numbers break."""

from app.monitoring import check_alerts

SUMMARY = {
    "requests": 40,
    "error_rate": 0.1,
    "p95_seconds": 4.2,
    "fallbacks": 0,
    "cost_usd": 0.02,
}
ERRORS = {
    "name": "Too many errors",
    "metric": "error_rate",
    "above": 0.05,
    "min_requests": 10,
    "action": "Read a failed trace",
}
SLOW = {"name": "Slow answers", "metric": "p95_seconds", "above": 3}


def test_a_rule_that_is_broken_fires_with_its_value_and_action():
    assert check_alerts(SUMMARY, [ERRORS]) == [
        {
            "name": "Too many errors",
            "metric": "error_rate",
            "value": 0.1,
            "above": 0.05,
            "action": "Read a failed trace",
        }
    ]


def test_a_rule_that_is_kept_does_not_fire():
    assert (
        check_alerts(
            SUMMARY, [{"name": "Fallbacks", "metric": "fallbacks", "above": 0}]
        )
        == []
    )
    assert (
        check_alerts({**SUMMARY, "error_rate": 0.05}, [ERRORS]) == []
    )  # "above" means greater than


def test_too_few_requests_means_no_alert_yet():
    assert check_alerts({**SUMMARY, "requests": 3}, [ERRORS]) == []


def test_a_missing_or_empty_metric_is_skipped():
    assert (
        check_alerts(SUMMARY, [{"name": "?", "metric": "nonsense", "above": 1}]) == []
    )
    assert check_alerts({**SUMMARY, "p95_seconds": None}, [SLOW]) == []


def test_several_rules_fire_in_order_and_action_defaults_to_empty():
    fired = check_alerts(SUMMARY, [ERRORS, SLOW])
    assert [a["name"] for a in fired] == ["Too many errors", "Slow answers"]
    assert fired[1]["action"] == "" and fired[1]["value"] == 4.2
