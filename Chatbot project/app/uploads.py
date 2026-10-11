"""Adding a document from the browser: check it BEFORE saving anything, then save it and read its scanned pages.

Every check is plain code with no model. A file is judged by its bytes, not its name; the name is cleaned to plain characters; an
existing document is never overwritten; and the cost of reading scanned pages is shown before anything is spent.
"""
import io
import re
from pathlib import Path

from pypdf import PdfReader

from app.config import DOCS_DIR, MAX_UPLOAD_BYTES, TRANSCRIPTS_DIR
from app.llm import call_vision
from app.scanned import MIN_TEXT_CHARS, estimate, transcribe_pdf

ALLOWED = {".pdf": "pdf", ".txt": "text", ".md": "text"}
NAME_CHARS = re.compile(r"[^A-Za-z0-9._ -]")


class UploadError(ValueError):
    """The file cannot be added. The message is friendly and safe to show."""


def safe_name(name: str) -> str:
    """Just the file name, with only plain characters, and a supported ending. Raises UploadError otherwise."""
    base = Path(str(name).replace("\\", "/")).name  # no folders: "../../x.pdf" becomes "x.pdf"
    cleaned = NAME_CHARS.sub("_", base).strip(" .")[:80]
    suffix = Path(cleaned).suffix.lower()
    if suffix not in ALLOWED or not Path(cleaned).stem.strip("_ "):
        raise UploadError("Only .pdf, .txt and .md files can be added, and the file needs a name.")
    return cleaned


def inspect_upload(name: str, data: bytes, docs_dir: Path = DOCS_DIR) -> dict:
    """Check an upload without saving it. Returns {name, kind, pages, picture_pages, calls, cost_usd, needs_confirm}.

    Raises UploadError for: an empty file, one over the size limit, a name that already exists, a PDF that is not really a PDF or cannot
    be read, and a text file that is not UTF-8 or has nothing in it.
    """
    if not data:
        raise UploadError("That file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadError(f"That file is bigger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    clean = safe_name(name)
    if (Path(docs_dir) / clean).exists():
        raise UploadError(f"A document called {clean} is already in the knowledge base. Rename the file to add it as a new one.")
    kind = ALLOWED[Path(clean).suffix.lower()]
    if kind == "pdf":
        if not data.startswith(b"%PDF-"):
            raise UploadError("That file is not really a PDF.")
        try:
            reader = PdfReader(io.BytesIO(data))
            pictures = sum(1 for page in reader.pages if len((page.extract_text() or "").strip()) < MIN_TEXT_CHARS)
            pages = len(reader.pages)
        except Exception as err:  # noqa: BLE001: pypdf raises many kinds of error for damaged files
            raise UploadError("That PDF could not be read. It may be damaged or locked.") from err
        if pages == 0:
            raise UploadError("That PDF has no pages.")
    else:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as err:
            raise UploadError("That text file is not UTF-8, so it cannot be read.") from err
        if not text.strip():
            raise UploadError("That file has no text in it.")
        pages, pictures = 1, 0
    return {"name": clean, "kind": kind, "pages": pages, "picture_pages": pictures, **estimate(pictures)}


def add_upload(name: str, data: bytes, docs_dir: Path = DOCS_DIR, vision=call_vision, cache_dir: Path = TRANSCRIPTS_DIR, progress=None) -> dict:
    """Check, save and (for a scanned PDF) read the pages that are only pictures. Returns {name, picture_pages, read, failed}.

    `failed` is the first page the vision model could not be reached for (or None). The pages read before it stay saved, and the file
    stays in the knowledge base, so reading the remaining pages later picks up where this stopped.
    """
    plan = inspect_upload(name, data, docs_dir)
    docs_dir = Path(docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)
    target = docs_dir / plan["name"]
    target.write_bytes(data)
    summary = {"name": plan["name"], "picture_pages": plan["picture_pages"], "read": [], "failed": None}
    if plan["picture_pages"]:
        outcome = transcribe_pdf(target, vision, cache_dir, progress=progress)
        summary["read"], summary["failed"] = outcome["read"], outcome["failed"]
    return summary


def read_unread_pages(docs_dir: Path = DOCS_DIR, vision=call_vision, cache_dir: Path = TRANSCRIPTS_DIR, progress=None) -> dict:
    """Read every picture-only page of every PDF in the knowledge base that has not been read yet. Returns {read, failed}."""
    from app.scanned import pages_to_read
    result = {"read": 0, "failed": None}
    for pdf in sorted(Path(docs_dir).glob("*.pdf")):
        if not pages_to_read(pdf, cache_dir):
            continue
        outcome = transcribe_pdf(pdf, vision, cache_dir, progress=progress)
        result["read"] += len(outcome["read"])
        if outcome["failed"] is not None:
            result["failed"] = (pdf.name, outcome["failed"])
            break
    return result
