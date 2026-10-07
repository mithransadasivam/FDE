"""Tells you when Activity 3 is done: all five tests pass. The model is a fake."""

from app.rerank import rerank
from tests.day07_fakes import FakeChatClient, chunk

A, B, C = chunk("a"), chunk("b"), chunk("c")


def test_chunks_are_reordered_by_the_models_scores():
    result = rerank("q", [A, B, C], client=FakeChatClient("[2, 9, 5]"))
    assert [c["id"] for c in result] == ["b", "c", "a"]


def test_only_top_n_are_kept():
    result = rerank("q", [A, B, C], top_n=2, client=FakeChatClient("[2, 9, 5]"))
    assert [c["id"] for c in result] == ["b", "c"]


def test_each_chunk_gets_its_score_and_the_inputs_are_not_changed():
    result = rerank("q", [A, B, C], client=FakeChatClient("[2, 9, 5]"))
    assert [c["rerank_score"] for c in result] == [9, 5, 2]
    assert "rerank_score" not in A


def test_equal_scores_keep_the_original_order():
    result = rerank("q", [A, B, C], client=FakeChatClient("[5, 5, 5]"))
    assert [c["id"] for c in result] == ["a", "b", "c"]


def test_no_chunks_means_no_model_call():
    fake = FakeChatClient("[1]")
    assert rerank("q", [], client=fake) == []
    assert fake.calls == []
