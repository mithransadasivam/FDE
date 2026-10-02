"""Tells you when Activity 1 is done: all five tests pass. No model is used."""

import numpy as np
import pytest

from app.embeddings import cosine_similarity


def test_same_vector_scores_one():
    assert cosine_similarity(
        np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0])
    ) == pytest.approx(1.0)


def test_unrelated_directions_score_zero():
    assert cosine_similarity(
        np.array([1.0, 0.0]), np.array([0.0, 1.0])
    ) == pytest.approx(0.0)


def test_opposite_directions_score_minus_one():
    assert cosine_similarity(
        np.array([1.0, 1.0]), np.array([-1.0, -1.0])
    ) == pytest.approx(-1.0)


def test_length_does_not_matter_only_direction():
    assert cosine_similarity(
        np.array([1.0, 2.0]), np.array([10.0, 20.0])
    ) == pytest.approx(1.0)


def test_a_worked_example():
    # dot = 3*4 + 4*3 = 24; lengths are 5 and 5; 24 / 25 = 0.96
    assert cosine_similarity(
        np.array([3.0, 4.0]), np.array([4.0, 3.0])
    ) == pytest.approx(0.96)
