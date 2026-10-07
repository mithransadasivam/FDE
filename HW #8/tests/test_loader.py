import pytest

from app.loader import load_documents


def test_loads_txt_and_md_as_one_page(tmp_path):
    (tmp_path / "a.md").write_text("# Title\nhello", encoding="utf-8")
    (tmp_path / "b.txt").write_text("plain", encoding="utf-8")
    (tmp_path / "ignore.docx").write_text("x")
    docs = load_documents(tmp_path)
    assert [d["source"] for d in docs] == ["a.md", "b.txt"]
    assert docs[0]["type"] == "Markdown" and docs[0]["pages"] == [(1, "# Title\nhello")]


def test_unreadable_file_is_reported_not_fatal(tmp_path):
    (tmp_path / "bad.txt").write_bytes(b"\xff\xfe\x00bad\x80")
    (tmp_path / "good.txt").write_text("fine", encoding="utf-8")
    docs = {d["source"]: d for d in load_documents(tmp_path)}
    assert docs["bad.txt"]["pages"] == [] and docs["bad.txt"]["warning"]
    assert docs["good.txt"]["pages"] == [(1, "fine")]


def test_missing_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_documents(tmp_path / "nope")


# ---- real PDF files (built in the test, no files needed) ----
from pypdf import PdfWriter

from app.chunker import chunk_document


def make_pdf(path, pages):
    """Write a small valid PDF with one line of text per page."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    font_obj = 3 + 2 * len(pages)
    for i, text in enumerate(pages):
        page_obj, content_obj = 3 + 2 * i, 4 + 2 * i
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents {content_obj} 0 R "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> >>".encode()
        )
        stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode()
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))


def test_pdf_pages_keep_their_page_numbers(tmp_path):
    make_pdf(tmp_path / "guide.pdf", ["First page about VPN", "Second page about MFA"])
    (doc,) = load_documents(tmp_path)
    assert doc["type"] == "PDF" and doc["warning"] == ""
    assert [n for n, _ in doc["pages"]] == [1, 2]
    assert "VPN" in doc["pages"][0][1] and "MFA" in doc["pages"][1][1]
    chunks = chunk_document(doc)
    assert [(c["page"], "VPN" in c["text"]) for c in chunks] == [(1, True), (2, False)]


def test_scanned_pdf_without_text_gives_no_chunks(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)  # like a scanned image: a page with no text layer
    with open(tmp_path / "scan.pdf", "wb") as f:
        writer.write(f)
    (doc,) = load_documents(tmp_path)
    assert len(doc["pages"]) == 1 and chunk_document(doc) == []


def test_corrupt_pdf_is_reported_not_fatal(tmp_path):
    (tmp_path / "broken.pdf").write_bytes(b"this is not a pdf at all")
    (tmp_path / "ok.txt").write_text("fine", encoding="utf-8")
    docs = {d["source"]: d for d in load_documents(tmp_path)}
    assert docs["broken.pdf"]["pages"] == [] and docs["broken.pdf"]["warning"]
    assert docs["ok.txt"]["pages"] == [(1, "fine")]
