"""Adding a document from the browser: every check runs before anything is saved, and a failure never loses what was already read."""
import pytest

from app.config import MAX_UPLOAD_BYTES, MAX_VISION_PAGES
from app.scanned import load_transcripts, file_hash
from app.uploads import UploadError, add_upload, inspect_upload, read_unread_pages, safe_name
from tests.test_scanned import TEXT_PDF, Vision, make_scan


def scan_bytes(tmp_path, pages=2, label="A"):
    return make_scan(tmp_path / f"made_{label}_{pages}.pdf", pages, label).read_bytes()


# --- names ------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw,clean", [("../../evil.pdf", "evil.pdf"), ("..\\..\\evil.md", "evil.md"), ("my file (1).txt", "my file _1_.txt"),
                                       ("rép<>ort.pdf", "r_p__ort.pdf"), ("NOTES.MD", "NOTES.MD")])
def test_a_name_is_cut_down_to_a_plain_file_name(raw, clean):
    assert safe_name(raw) == clean


@pytest.mark.parametrize("raw", ["", "..", "x.exe", "noending", ".pdf", "___.pdf", "a.pdf.exe"])
def test_a_name_that_is_not_a_supported_document_is_refused(raw):
    with pytest.raises(UploadError):
        safe_name(raw)


# --- checks before saving ---------------------------------------------------------------------------------------------------------

def test_a_good_scan_is_inspected_with_its_price_and_nothing_is_saved(tmp_path):
    docs = tmp_path / "docs"
    plan = inspect_upload("scan.pdf", scan_bytes(tmp_path, 3), docs)
    assert plan["kind"] == "pdf" and plan["pages"] == 3 and plan["picture_pages"] == 3 and plan["calls"] == 3 and plan["cost_usd"] > 0
    assert plan["needs_confirm"] is False and not docs.exists()


def test_a_text_pdf_needs_no_vision_calls():
    plan = inspect_upload("policy.pdf", TEXT_PDF.read_bytes(), TEXT_PDF.parent.parent / "nowhere")
    assert plan["picture_pages"] == 0 and plan["calls"] == 0 and plan["cost_usd"] == 0 and plan["needs_confirm"] is False


def test_a_long_scan_must_be_confirmed(tmp_path):
    assert inspect_upload("long.pdf", scan_bytes(tmp_path, MAX_VISION_PAGES + 1), tmp_path)["needs_confirm"] is True


def test_a_text_file_is_one_page_and_free(tmp_path):
    plan = inspect_upload("note.md", b"# Note\nBackups are kept 30 days.", tmp_path)
    assert plan["kind"] == "text" and plan["pages"] == 1 and plan["calls"] == 0


@pytest.mark.parametrize("name,data,words", [
    ("a.pdf", b"", "empty"),
    ("a.pdf", b"x" * (MAX_UPLOAD_BYTES + 1), "bigger"),
    ("a.pdf", b"just text, not a pdf", "not really a PDF"),
    ("a.pdf", b"%PDF-1.4 broken", "could not be read"),
    ("a.txt", b"\xff\xfe\x00bad", "UTF-8"),
    ("a.txt", b"   \n  ", "no text"),
    ("a.exe", b"MZ...", "Only .pdf"),
], ids=["empty", "too-big", "not-a-pdf", "broken-pdf", "not-utf8", "blank-text", "wrong-type"])
def test_a_bad_file_is_refused_with_a_friendly_reason(tmp_path, name, data, words):
    with pytest.raises(UploadError, match=words):
        inspect_upload(name, data, tmp_path)


def test_a_file_is_judged_by_its_bytes_not_its_name(tmp_path):
    with pytest.raises(UploadError):
        inspect_upload("holiday.pdf", b"<html>pretending</html>", tmp_path)


def test_an_existing_document_is_never_overwritten(tmp_path):
    (tmp_path / "keep.md").write_text("original", encoding="utf-8")
    with pytest.raises(UploadError, match="already in the knowledge base"):
        add_upload("keep.md", b"replacement", tmp_path, vision=Vision(), cache_dir=tmp_path / "t")
    assert (tmp_path / "keep.md").read_text(encoding="utf-8") == "original"


# --- saving and reading -----------------------------------------------------------------------------------------------------------

def test_a_scan_is_saved_and_its_pages_are_read(tmp_path):
    docs, cache, data = tmp_path / "docs", tmp_path / "t", scan_bytes(tmp_path, 2)
    vision = Vision(["One", "Two"])
    summary = add_upload("scan.pdf", data, docs, vision=vision, cache_dir=cache)
    assert summary == {"name": "scan.pdf", "picture_pages": 2, "read": [1, 2], "failed": None}
    assert (docs / "scan.pdf").read_bytes() == data and len(vision.calls) == 2
    assert load_transcripts(file_hash(data), cache) == {1: "One", 2: "Two"}


def test_a_text_file_is_saved_without_any_vision_call(tmp_path):
    vision = Vision()
    summary = add_upload("note.txt", b"Hello there", tmp_path / "docs", vision=vision, cache_dir=tmp_path / "t")
    assert summary["read"] == [] and vision.calls == [] and (tmp_path / "docs" / "note.txt").read_bytes() == b"Hello there"


def test_a_bad_file_leaves_the_folder_untouched(tmp_path):
    docs = tmp_path / "docs"
    with pytest.raises(UploadError):
        add_upload("bad.pdf", b"nope", docs, vision=Vision(), cache_dir=tmp_path / "t")
    assert not docs.exists()


def test_a_failure_halfway_keeps_the_file_and_the_pages_already_read(tmp_path):
    docs, cache, data = tmp_path / "docs", tmp_path / "t", scan_bytes(tmp_path, 3)
    summary = add_upload("scan.pdf", data, docs, vision=Vision(["One"], fail_on_call=2), cache_dir=cache)
    assert summary["read"] == [1] and summary["failed"] == 2 and (docs / "scan.pdf").exists()
    assert load_transcripts(file_hash(data), cache) == {1: "One"}


def test_reading_the_remaining_pages_reads_only_what_is_missing(tmp_path):
    docs, cache = tmp_path / "docs", tmp_path / "t"
    add_upload("scan.pdf", scan_bytes(tmp_path, 3), docs, vision=Vision(["One"], fail_on_call=2), cache_dir=cache)
    vision = Vision(["Two", "Three"])
    assert read_unread_pages(docs, vision, cache) == {"read": 2, "failed": None} and len(vision.calls) == 2
    again = Vision()
    assert read_unread_pages(docs, again, cache) == {"read": 0, "failed": None} and again.calls == []


def test_reading_the_remaining_pages_stops_and_says_where_it_failed(tmp_path):
    docs, cache = tmp_path / "docs", tmp_path / "t"
    docs.mkdir()
    (docs / "a.pdf").write_bytes(scan_bytes(tmp_path, 2, "A"))
    (docs / "b.pdf").write_bytes(scan_bytes(tmp_path, 2, "B"))
    result = read_unread_pages(docs, Vision(fail_on_call=1), cache)
    assert result == {"read": 0, "failed": ("a.pdf", 1)}
