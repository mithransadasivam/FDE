"""Tells you when Activity 2 is done: all six tests pass. No model is used."""

import pytest

from app.indexing import chunk_text

TEXT = "".join(
    chr(ord("a") + i % 26) for i in range(1200)
)  # 1,200 characters, easy to check


def test_no_piece_is_longer_than_size():
    assert all(len(c) <= 500 for c in chunk_text(TEXT, size=500, overlap=100))


def test_neighbouring_pieces_share_the_overlap():
    chunks = chunk_text(TEXT, size=500, overlap=100)
    assert chunks[0][-100:] == chunks[1][:100]


def test_the_whole_text_is_covered():
    chunks = chunk_text(TEXT, size=500, overlap=100)
    assert chunks[0].startswith(TEXT[:50]) and chunks[-1].endswith(TEXT[-50:])
    assert len(chunks) == 3  # pieces start at 0, 400 and 800


def test_short_text_is_one_piece():
    assert chunk_text("Short policy text.", size=500, overlap=100) == [
        "Short policy text."
    ]


def test_empty_text_gives_no_pieces():
    assert chunk_text("   ", size=500, overlap=100) == []


def test_overlap_must_be_smaller_than_size():
    with pytest.raises(ValueError):
        chunk_text(TEXT, size=100, overlap=100)
