"""Day 18, Activity 3: card_gaps() lists everything that stops the model card being complete."""

import json

from app.model_card import REQUIRED, card_gaps


def full_card(tmp_path):
    (tmp_path / "ev").mkdir()
    (tmp_path / "ev" / "report.json").write_text("{}")
    card = {k: f"some {k}" for k in REQUIRED}
    card["evaluation"] = [
        {"metric": "Hit rate", "value": "0.95", "source": "ev/report.json"}
    ]
    card["limitations"] = ["one", "two", "three"]
    return card


def test_a_complete_card_has_no_gaps(tmp_path):
    assert card_gaps(full_card(tmp_path), root=str(tmp_path)) == []


def test_missing_and_todo_sections_are_listed_in_order(tmp_path):
    card = full_card(tmp_path)
    card["purpose"] = "TODO: write this"
    del card["contact"]
    card["human_oversight"] = []
    assert card_gaps(card, root=str(tmp_path)) == [
        "missing: purpose",
        "missing: human_oversight",
        "missing: contact",
    ]


def test_every_result_needs_its_evidence(tmp_path):
    card = full_card(tmp_path)
    card["evaluation"] += [
        {"metric": "Bias", "value": "", "source": "ev/bias.json"},
        {"metric": "Red team", "value": "1 of 15", "source": "ev/red_team.json"},
    ]
    assert card_gaps(card, root=str(tmp_path)) == [
        "evaluation 2: needs metric, value and source",
        "evaluation 3: no evidence at ev/red_team.json",
    ]


def test_at_least_three_limitations(tmp_path):
    card = full_card(tmp_path)
    card["limitations"] = ["only one"]
    assert card_gaps(card, root=str(tmp_path)) == ["limitations: at least 3"]


def test_the_starter_card_shows_its_gaps():
    with open("governance/model_card.json", encoding="utf-8") as f:
        card = json.load(f)
    gaps = card_gaps(card)
    assert all(isinstance(g, str) for g in gaps)
    assert card_gaps({})[:2] == ["missing: name", "missing: version"]
