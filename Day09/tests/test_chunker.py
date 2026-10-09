import pytest

from app.chunker import chunk_document, chunk_text


def test_chunks_never_exceed_size():
    chunks = chunk_text("word " * 500, size=100, overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)


def test_neighbouring_chunks_overlap():
    text = "".join(str(i % 10) for i in range(300))
    chunks = chunk_text(text, size=100, overlap=30)
    assert chunks[0][-30:] == chunks[1][:30]


def test_short_text_gives_one_chunk():
    assert chunk_text("Hello there", size=100, overlap=20) == ["Hello there"]


def test_text_exactly_size_gives_one_chunk():
    assert len(chunk_text("a" * 100, size=100, overlap=20)) == 1


def test_empty_and_whitespace_text_give_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\t ") == []


def test_all_text_is_covered():
    text = "".join(chr(97 + i % 26) for i in range(1000))
    chunks = chunk_text(text, size=100, overlap=10)
    assert chunks[0].startswith(text[:10])
    assert chunks[-1].endswith(text[-10:])


@pytest.mark.parametrize("size,overlap", [(0, 0), (-5, 0), (100, -1), (100, 100), (100, 150)])
def test_invalid_settings_raise(size, overlap):
    with pytest.raises(ValueError):
        chunk_text("some text", size=size, overlap=overlap)


def test_chunk_document_keeps_source_page_and_numbers():
    doc = {"source": "guide.pdf", "pages": [(1, "a" * 150), (2, "   "), (3, "b" * 50)]}
    chunks = chunk_document(doc, size=100, overlap=20)
    assert [c["page"] for c in chunks] == [1, 1, 3]
    assert [c["chunk"] for c in chunks] == [1, 2, 3]
    assert all(c["source"] == "guide.pdf" for c in chunks)


def test_document_with_no_text_gives_no_chunks():
    assert chunk_document({"source": "scan.pdf", "pages": [(1, ""), (2, "")]}) == []
