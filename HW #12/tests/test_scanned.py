"""Tells you when Activity 3 is done: all five tests pass. The vision model is a fake."""

from pypdf import PdfWriter

from app.scanned import load_pages_smart
from tests.day10_fakes import FakeChatClient

TEXT_PDF = "data/policies/Day06_Slide15_policy_vpn_remote_access.pdf"
SCANNED_PDF = "data/policies/Day10_Slide21_policy_printing_scanned.pdf"


def test_pages_with_text_are_read_without_calling_the_model():
    fake = FakeChatClient("should not be used")
    pages = load_pages_smart(TEXT_PDF, client=fake)
    assert [m for _, _, m in pages] == ["text", "text"] and "12 hours" in pages[0][1]
    assert fake.calls == []


def test_scanned_pages_are_transcribed_one_call_per_page():
    fake = FakeChatClient("Printing and Scanning Policy ... 200 colour pages per month")
    pages = load_pages_smart(SCANNED_PDF, client=fake)
    assert [(n, m) for n, _, m in pages] == [(1, "vision"), (2, "vision")]
    assert "200 colour pages" in pages[0][1] and len(fake.calls) == 2


def test_the_scanned_image_is_sent_as_a_jpeg_data_url():
    fake = FakeChatClient("text")
    load_pages_smart(SCANNED_PDF, client=fake)
    parts = fake.calls[0]["messages"][0]["content"]
    assert any(
        p.get("type") == "image_url"
        and p["image_url"]["url"].startswith("data:image/jpeg;base64,")
        for p in parts
    )


def test_a_markdown_file_is_one_text_page(tmp_path):
    md = tmp_path / "note.md"
    md.write_text("# VPN\nSessions last 12 hours.", encoding="utf-8")
    assert load_pages_smart(md, client=FakeChatClient("unused")) == [
        (1, "# VPN\nSessions last 12 hours.", "text")
    ]


def test_a_blank_page_is_empty_with_no_model_call(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    pdf = tmp_path / "blank.pdf"
    with open(pdf, "wb") as f:
        writer.write(f)
    fake = FakeChatClient("unused")
    assert load_pages_smart(pdf, client=fake) == [(1, "", "empty")]
    assert fake.calls == []
