import pytest
from pydantic import ValidationError

from app.schemas import BlindCandidate, Rubric, RubricItem


def items(weights):
    return [RubricItem(skill=f"Skill {i}", weight=w, evidence_from_note=f"words {i}") for i, w in enumerate(weights)]


def test_weights_adding_to_100_are_accepted():
    assert Rubric(items=items([20, 20, 20, 20, 20]), min_years=2).total == 100


def test_weights_adding_to_90_are_rejected():
    with pytest.raises(ValidationError, match="must add to 100, got 90"):
        Rubric(items=items([20, 20, 20, 20, 10]), min_years=2)


def test_duplicate_skill_is_rejected():
    its = items([20, 20, 20, 20, 20])
    its[1].skill = " skill 0 "
    with pytest.raises(ValidationError, match="duplicate skill"):
        Rubric(items=its, min_years=1)


def test_too_few_items_rejected():
    with pytest.raises(ValidationError):
        Rubric(items=items([50, 50]), min_years=1)


def test_weight_over_40_rejected():
    with pytest.raises(ValidationError):
        RubricItem(skill="Linux", weight=41, evidence_from_note="linux")


def test_blind_candidate_has_no_identity_fields():
    for f in ("name", "email", "phone", "address", "date_of_birth"):
        assert f not in BlindCandidate.model_fields
