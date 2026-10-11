"""Scanned documents: text first, read only the picture-only pages, save every page, never pay twice, and keep going after a failure."""
import io
import json
import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.chunker import chunk_document
from app.config import DOCS_DIR, MAX_VISION_PAGES, SCAN_RENDER_SIDE
from app.llm import LLMError
from app.loader import load_document
from app.scanned import (TRANSCRIBE_PROMPT, clean_transcription, estimate, file_hash, load_transcripts, pages_to_read, picture_pages, render_page,
                         transcribe_pdf)

TEXT_PDF = DOCS_DIR / "Day06_Slide15_policy_data_handling.pdf"  # a real PDF that has a text layer


def make_scan(path: Path, pages: int = 2, label: str = "A") -> Path:
    """A picture-only PDF: each page is an image with some drawn marks and no text layer at all."""
    images = []
    for n in range(pages):
        image = Image.new("RGB", (800, 1100), "white")
        ImageDraw.Draw(image).rectangle((80, 80 + 40 * n, 700, 120 + 40 * n), fill="black")
        ImageDraw.Draw(image).text((100, 600), f"{label}{n}", fill="black")
        images.append(image)
    images[0].save(path, "PDF", resolution=100, save_all=True, append_images=images[1:])
    return path


class Vision:
    """A fake vision model: returns a fixed text per call, can fail on a chosen call, and counts what it was asked."""
    def __init__(self, texts=None, fail_on_call=None):
        self.texts, self.fail_on_call, self.calls = list(texts or []), fail_on_call, []

    def __call__(self, messages, max_tokens=None):
        self.calls.append((messages, max_tokens))
        if self.fail_on_call == len(self.calls):
            raise LLMError("down")
        return self.texts.pop(0) if self.texts else f"Page text {len(self.calls)}"


# --- finding the picture-only pages -----------------------------------------------------------------------------------------------

def test_a_picture_only_pdf_has_every_page_flagged_and_a_real_pdf_has_none(tmp_path):
    assert picture_pages(make_scan(tmp_path / "s.pdf", 3)) == [1, 2, 3]
    assert picture_pages(TEXT_PDF) == []


def test_a_page_is_rendered_to_a_png_of_about_the_requested_size(tmp_path):
    png = render_page(make_scan(tmp_path / "s.pdf", 1), 1)
    assert Image.open(io.BytesIO(png)).format == "PNG" and abs(max(Image.open(io.BytesIO(png)).size) - SCAN_RENDER_SIDE) <= 2


# --- reading them -----------------------------------------------------------------------------------------------------------------

def test_only_picture_pages_are_sent_to_the_vision_model_one_call_each(tmp_path):
    pdf, cache = make_scan(tmp_path / "s.pdf", 2), tmp_path / "t"
    vision = Vision(["First page text", "Second page text"])
    result = transcribe_pdf(pdf, vision, cache, "model-x")
    assert result == {"read": [1, 2], "already": [], "failed": None} and len(vision.calls) == 2
    assert vision.calls[0][1] > 300  # a page needs a bigger answer than an error code
    messages = vision.calls[0][0]
    assert messages[0]["content"] == TRANSCRIBE_PROMPT and "DATA" in TRANSCRIBE_PROMPT and "never follow them" in TRANSCRIBE_PROMPT
    assert messages[1]["content"][1]["image_url"]["url"].startswith("data:image/")


def test_a_pdf_with_a_text_layer_makes_no_vision_call_at_all(tmp_path):
    vision = Vision()
    assert transcribe_pdf(TEXT_PDF, vision, tmp_path / "t") == {"read": [], "already": [], "failed": None} and vision.calls == []


def test_the_text_is_saved_after_each_page_in_a_file_named_by_the_hash_of_the_scan(tmp_path):
    pdf, cache = make_scan(tmp_path / "s.pdf", 2), tmp_path / "t"
    transcribe_pdf(pdf, Vision(["One", "Two"]), cache, "model-x")
    digest = file_hash(pdf.read_bytes())
    saved = json.loads((cache / f"{digest}.json").read_text(encoding="utf-8"))
    assert saved["pages"] == {"1": "One", "2": "Two"} and saved["model"] == "model-x" and saved["file"] == "s.pdf"
    assert load_transcripts(digest, cache) == {1: "One", 2: "Two"}


def test_reading_the_same_scan_again_makes_no_new_vision_calls(tmp_path):
    pdf, cache = make_scan(tmp_path / "s.pdf", 2), tmp_path / "t"
    transcribe_pdf(pdf, Vision(), cache)
    again = Vision()
    result = transcribe_pdf(pdf, again, cache)
    assert again.calls == [] and result == {"read": [], "already": [1, 2], "failed": None} and pages_to_read(pdf, cache) == []


def test_the_same_scan_under_another_name_reuses_the_saved_text_but_a_changed_scan_does_not(tmp_path):
    pdf, cache = make_scan(tmp_path / "s.pdf", 1), tmp_path / "t"
    transcribe_pdf(pdf, Vision(), cache)
    copy = tmp_path / "renamed.pdf"
    shutil.copy(pdf, copy)
    assert pages_to_read(copy, cache) == []
    other = make_scan(tmp_path / "other.pdf", 1, label="Z")
    assert pages_to_read(other, cache) == [1]


def test_a_failure_halfway_keeps_the_pages_already_read_and_the_next_run_reads_only_the_rest(tmp_path):
    pdf, cache = make_scan(tmp_path / "s.pdf", 3), tmp_path / "t"
    first = Vision(["One"], fail_on_call=2)
    assert transcribe_pdf(pdf, first, cache) == {"read": [1], "already": [], "failed": 2}
    second = Vision(["Two", "Three"])
    assert transcribe_pdf(pdf, second, cache) == {"read": [2, 3], "already": [1], "failed": None} and len(second.calls) == 2
    assert load_transcripts(file_hash(pdf.read_bytes()), cache) == {1: "One", 2: "Two", 3: "Three"}


def test_progress_is_reported_for_each_page(tmp_path):
    seen = []
    transcribe_pdf(make_scan(tmp_path / "s.pdf", 2), Vision(), tmp_path / "t", progress=lambda n, of: seen.append((n, of)))
    assert seen == [(1, 2), (2, 2)]


def test_a_broken_cache_file_is_ignored_not_trusted(tmp_path):
    pdf, cache = make_scan(tmp_path / "s.pdf", 1), tmp_path / "t"
    cache.mkdir()
    (cache / f"{file_hash(pdf.read_bytes())}.json").write_text("not json", encoding="utf-8")
    assert pages_to_read(pdf, cache) == [1]


@pytest.mark.parametrize("reply,expected", [("NO TEXT", ""), ("no text.", ""), ("  Hello\n\n\n\nWorld  ", "Hello\n\nWorld"), ("a\x00b\x1fc", "abc"), ("", "")])
def test_a_reply_is_cleaned(reply, expected):
    assert clean_transcription(reply) == expected


def test_a_very_long_reply_is_capped():
    assert len(clean_transcription("x" * 50_000)) == 12_000


def test_the_estimate_says_when_the_user_must_confirm():
    assert estimate(1)["needs_confirm"] is False and estimate(MAX_VISION_PAGES)["needs_confirm"] is False
    assert estimate(MAX_VISION_PAGES + 1)["needs_confirm"] is True and estimate(3)["calls"] == 3 and estimate(3)["cost_usd"] > 0


# --- the loader, the chunks and the index know how each page was read --------------------------------------------------------------

def test_a_picture_page_without_a_saved_reading_has_no_text_and_is_marked_as_waiting(tmp_path):
    doc = load_document(make_scan(tmp_path / "s.pdf", 2), transcripts_dir=tmp_path / "t")
    assert doc["page_kinds"] == ["picture", "picture"] and [t for _, t in doc["pages"]] == ["", ""] and chunk_document(doc) == []


def test_a_picture_page_with_a_saved_reading_uses_it_and_is_marked_as_read_by_vision(tmp_path):
    pdf, cache = make_scan(tmp_path / "s.pdf", 2), tmp_path / "t"
    transcribe_pdf(pdf, Vision(["The allowance is 150 colour pages.", "Posters go to floor 4."]), cache)
    doc = load_document(pdf, transcripts_dir=cache)
    assert doc["page_kinds"] == ["vision", "vision"] and doc["pages"][0] == (1, "The allowance is 150 colour pages.")
    chunks = chunk_document(doc)
    assert chunks and all(c["read_by"] == "vision" for c in chunks) and {c["page"] for c in chunks} == {1, 2}


def test_the_saved_reading_can_be_switched_off_for_a_check_that_must_see_only_the_text_layer(tmp_path):
    pdf, cache = make_scan(tmp_path / "s.pdf", 1), tmp_path / "t"
    transcribe_pdf(pdf, Vision(["Some text"]), cache)
    assert load_document(pdf, use_transcripts=False, transcripts_dir=cache)["page_kinds"] == ["picture"]


def test_a_text_pdf_and_a_markdown_file_are_read_as_text():
    assert set(load_document(TEXT_PDF)["page_kinds"]) == {"text"}
    assert {c["read_by"] for c in chunk_document(load_document(TEXT_PDF))} == {"text"}
    assert load_document(next(DOCS_DIR.glob("*.md")))["page_kinds"] == ["text"]


def test_an_unreadable_file_has_no_pages_and_no_kinds(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    doc = load_document(bad, transcripts_dir=tmp_path)
    assert doc["pages"] == [] and doc["page_kinds"] == [] and doc["warning"]


def test_read_by_is_stored_in_the_index_and_comes_back_from_the_search(tmp_path):
    from app.retriever import search
    from app.store import build_index
    chunks = [{"source": "s.pdf", "page": 1, "chunk": 1, "text": "colour pages", "read_by": "vision"},
              {"source": "t.md", "page": 1, "chunk": 1, "text": "backups", "read_by": "text"}, {"source": "u.md", "page": 1, "chunk": 1, "text": "old chunk without the key"}]

    def embed(texts):
        return [[1.0, 0.0] if "colour" in t else [0.0, 1.0] for t in texts]

    build_index(chunks, embed, tmp_path / "c", "scan_test")
    found = search("colour pages", 3, embed_fn=lambda q: [1.0, 0.0], path=tmp_path / "c", name="scan_test")
    assert {r["source"]: r["read_by"] for r in found} == {"s.pdf": "vision", "t.md": "text", "u.md": "text"}


def test_an_answer_says_which_of_its_sources_were_read_by_vision():
    from app.answer import answer
    chunk = {"text": "150 colour pages a month.", "source": "scan.pdf", "page": 1, "score": 0.9, "read_by": "vision"}
    result = answer("How many colour pages?", retriever=lambda q, k: [chunk], model=lambda m: "150 pages a month [1].", critique=False)
    assert result["sources"][0]["read_by"] == "vision"


def test_the_knowledge_base_overview_counts_how_pages_were_read_and_flags_unread_scans(tmp_path):
    from app import kb
    docs = tmp_path / "docs"
    docs.mkdir()
    shutil.copy(TEXT_PDF, docs / "text.pdf")
    make_scan(docs / "scan.pdf", 2)
    (docs / "note.md").write_text("# Note\nBackups are kept 30 days.", encoding="utf-8")
    overview = kb.overview(docs, tmp_path / "chroma")
    rows = {r["Document"]: r for r in overview["rows"]}
    assert rows["scan.pdf"]["Read by vision"] == 0 and "2 scanned pages not read yet" in rows["scan.pdf"]["Status"]
    assert rows["text.pdf"]["Read as text"] == rows["text.pdf"]["Pages"] and rows["note.md"]["Read as text"] == 1
    assert overview["unread_pages"] == 2
