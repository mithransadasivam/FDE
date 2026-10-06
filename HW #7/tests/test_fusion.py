"""Tells you when Activity 2 is done: all five tests pass. No model or database is used."""

from app.hybrid import reciprocal_rank_fusion
from tests.day07_fakes import chunk

A, B, C, D = chunk("a"), chunk("b"), chunk("c"), chunk("d")


def test_one_list_keeps_its_order_and_scores_one_over_k_plus_position():
    fused = reciprocal_rank_fusion([A, B, C])
    assert [c["id"] for c in fused] == ["a", "b", "c"]
    assert abs(fused[0]["rrf"] - 1 / 61) < 1e-9 and abs(fused[2]["rrf"] - 1 / 63) < 1e-9


def test_a_chunk_found_by_both_searches_comes_first():
    fused = reciprocal_rank_fusion([A, B, C], [D, C])
    assert fused[0]["id"] == "c"
    assert abs(fused[0]["rrf"] - (1 / 63 + 1 / 62)) < 1e-9


def test_k_changes_the_scores():
    fused = reciprocal_rank_fusion([A], k=10)
    assert abs(fused[0]["rrf"] - 1 / 11) < 1e-9


def test_every_chunk_appears_once_and_equal_scores_keep_their_order():
    fused = reciprocal_rank_fusion([A, B], [C, D])
    assert [c["id"] for c in fused] == ["a", "c", "b", "d"]


def test_inputs_are_not_changed_and_empty_lists_give_nothing():
    first, second = [A, B], [B]
    reciprocal_rank_fusion(first, second)
    assert first == [A, B] and second == [B] and "rrf" not in A
    assert reciprocal_rank_fusion([], []) == []
