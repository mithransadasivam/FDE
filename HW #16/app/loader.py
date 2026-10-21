"""Load .pdf, .txt and .md files page by page."""
from pathlib import Path

from pypdf import PdfReader

from app.config import DOCS_DIR

SUPPORTED = {".pdf": "PDF", ".txt": "Text", ".md": "Markdown"}


def load_document(path: Path) -> dict:
    """Read one file. Returns {source, type, pages: [(page_number, text)], warning}.

    A file that cannot be read (corrupt, wrong encoding) is not an error for the
    whole run: it comes back with no pages and a warning. Page numbers start at 1;
    .txt and .md files are a single page.
    """
    doc = {"source": path.name, "type": SUPPORTED[path.suffix.lower()], "pages": [], "warning": ""}
    try:
        if path.suffix.lower() == ".pdf":
            reader = PdfReader(str(path))
            doc["pages"] = [(n, page.extract_text() or "") for n, page in enumerate(reader.pages, start=1)]
        else:
            doc["pages"] = [(1, path.read_text(encoding="utf-8"))]
    except Exception as err:  # unreadable file: report it, keep going
        doc["warning"] = f"could not read file: {type(err).__name__}"
    return doc


def load_documents(folder: Path = DOCS_DIR) -> list[dict]:
    """Load every supported file in a folder (sorted by name, not recursive)."""
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"Documents folder not found: {folder}")
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED)
    return [load_document(p) for p in files]
