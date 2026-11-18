"""Ticket ENG-601: parse one document into words, whatever form the bank sent it in.

The bank sends three kinds of file:
- a digital PDF: the words are in the PDF's text layer, exact, with their positions
- a scanned PDF: a picture of a page saved as a PDF; it has no text layer, so the words come from the bank's OCR file
- a JPG scan: a photo or scan of a page; the words come from the bank's OCR file

Both kinds of word list end up in the same shape (OcrWord), so everything after this step is the same.
"""

import json
from pathlib import Path

from app.pipeline.documents import document_file, ocr_file
from app.pipeline.models import ParsedPage
from app.prototype.models import OcrWord

MIN_TEXT_WORDS = 20  # a PDF with fewer words than this in its text layer is treated as a scan


def text_layer_words(pdf_path: Path) -> list[OcrWord]:
    """The words in the text layer of the PDF's first page, in reading order, as OcrWords.

    - Open the PDF with pdfplumber and take page 1's extract_words(x_tolerance=1.5, y_tolerance=3).
    - For each word, in the order pdfplumber gives them: id "w001", "w002"…; text as given;
      box = [x0 / width, top / height, x1 / width, bottom / height] of the page, each rounded to 4 decimals;
      confidence 1.0 (a text layer is exact: nothing was guessed).
    - A PDF with no text layer gives an empty list.
    """
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        width, height = float(page.width), float(page.height)
        raw = page.extract_words(x_tolerance=1.5, y_tolerance=3)
    return [
        OcrWord(
            id=f"w{i:03d}",
            text=w["text"],
            box=[round(w["x0"] / width, 4), round(w["top"] / height, 4), round(w["x1"] / width, 4), round(w["bottom"] / height, 4)],
            confidence=1.0,
        )
        for i, w in enumerate(raw, 1)
    ]

def ocr_file_words(doc_id: str) -> list[OcrWord]:
    """The words in the bank's OCR file for this document (data/…/<doc_id>.ocr.json)."""
    data = json.loads(ocr_file(doc_id).read_text(encoding="utf-8"))
    return [OcrWord(**w) for w in data["words"]]


def parse_document(doc_id: str) -> ParsedPage:
    """Parse one document.

    - file = document_file(doc_id) (raises KeyError for a document that is not in any set).
    - A .pdf: words = text_layer_words(file). With MIN_TEXT_WORDS words or more, source is "text_layer".
      Fewer: it is a scanned PDF, so words = ocr_file_words(doc_id) and source is "ocr".
    - A .jpg: words = ocr_file_words(doc_id), source "ocr".
    - Return ParsedPage(doc_id, file=the file's name, source, words).
    """
    file = document_file(doc_id)
    if file.suffix.lower() == ".pdf":
        words = text_layer_words(file)
        if len(words) >= MIN_TEXT_WORDS:
            return ParsedPage(doc_id=doc_id, file=file.name, source="text_layer", words=words)
    return ParsedPage(doc_id=doc_id, file=file.name, source="ocr", words=ocr_file_words(doc_id))
