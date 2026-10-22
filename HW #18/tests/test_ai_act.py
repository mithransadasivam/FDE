"""Day 18, Activity 1: classify_use_case() sorts use cases into EU AI Act risk categories, in order."""

import json

from app.ai_act import OBLIGATIONS, classify_use_case

PLAIN = {
    "practices": [],
    "annex_iii_area": None,
    "safety_component": False,
    "narrow_task": False,
    "profiles_people": False,
    "interacts_with_people": False,
    "generates_content": False,
}


def uc(**changes):
    return {**PLAIN, **changes}


def test_a_banned_practice_is_prohibited_even_in_a_high_risk_area():
    r = classify_use_case(
        uc(
            practices=["emotion_recognition_workplace"],
            annex_iii_area="employment",
            interacts_with_people=True,
        )
    )
    assert r["category"] == "prohibited" and r["reason"].startswith("Article 5(1)(f)")
    assert r["obligations"] == OBLIGATIONS["prohibited"]


def test_unknown_practice_tags_are_ignored():
    assert classify_use_case(uc(practices=["spell_checking"]))["category"] == "minimal"


def test_a_safety_component_is_high_risk():
    r = classify_use_case(uc(safety_component=True, interacts_with_people=True))
    assert r["category"] == "high" and "Annex I" in r["reason"]


def test_an_annex_iii_area_is_high_risk_with_its_point():
    r = classify_use_case(uc(annex_iii_area="employment", profiles_people=True))
    assert r == {
        "category": "high",
        "reason": "Annex III point 4: employment and workers management",
        "obligations": OBLIGATIONS["high"],
        "applies_from": "2 December 2027 (Annex III); 2 August 2028 (Annex I)",
    }


def test_a_narrow_task_escapes_annex_iii_unless_it_profiles_people():
    assert (
        classify_use_case(uc(annex_iii_area="education", narrow_task=True))["category"]
        == "minimal"
    )
    assert (
        classify_use_case(
            uc(annex_iii_area="education", narrow_task=True, profiles_people=True)
        )["category"]
        == "high"
    )


def test_a_chatbot_is_limited_risk_with_transparency_duties():
    r = classify_use_case(uc(interacts_with_people=True, generates_content=True))
    assert r["category"] == "limited" and r["reason"] == "Article 50: transparency"
    assert r["applies_from"] == "2 August 2026"


def test_the_class_inventory_and_missing_keys():
    with open("data/Day18_Slide09_use_cases.json", encoding="utf-8") as f:
        cases = json.load(f)
    assert [classify_use_case(c)["category"] for c in cases] == [
        "limited",
        "high",
        "prohibited",
        "minimal",
    ]
    assert classify_use_case({})["category"] == "minimal"
