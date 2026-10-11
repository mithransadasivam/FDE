"""Load .pdf, .txt and .md files page by page."""
from pathlib import Path

from pypdf import PdfReader

from app.config import DOCS_DIR, TRANSCRIPTS_DIR
from app.scanned import MIN_TEXT_CHARS, file_hash, load_transcripts

SUPPORTED = {".pdf": "PDF", ".txt": "Text", ".md": "Markdown"}


def load_document(path: Path, use_transcripts: bool = True, transcripts_dir: Path = TRANSCRIPTS_DIR) -> dict:
    """Read one file. Returns {source, type, pages: [(page_number, text)], page_kinds, warning}.

    `page_kinds` says how each page was read: "text" (the file's own text), "vision" (a picture-only PDF page whose saved transcription is used)
    or "picture" (a picture-only page nobody has read yet, so it has no text). Loading never calls a model.

    A file that cannot be read (corrupt, wrong encoding) is not an error for the
    whole run: it comes back with no pages and a warning. Page numbers start at 1;
    .txt and .md files are a single page.
    """
    doc = {"source": path.name, "type": SUPPORTED[path.suffix.lower()], "pages": [], "page_kinds": [], "warning": ""}
    try:
        if path.suffix.lower() == ".pdf":
            reader = PdfReader(str(path))
            transcripts = load_transcripts(file_hash(path.read_bytes()), transcripts_dir) if use_transcripts else {}
            for n, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                if len(text.strip()) >= MIN_TEXT_CHARS:
                    kind = "text"
                elif n in transcripts:
                    text, kind = transcripts[n], "vision"
                else:
                    kind = "picture"
                doc["pages"].append((n, text))
                doc["page_kinds"].append(kind)
        else:
            doc["pages"] = [(1, path.read_text(encoding="utf-8"))]
            doc["page_kinds"] = ["text"]
    except Exception as err:  # unreadable file: report it, keep going
        doc["pages"], doc["page_kinds"] = [], []
        doc["warning"] = f"could not read file: {type(err).__name__}"
    return doc


def load_documents(folder: Path = DOCS_DIR, use_transcripts: bool = True) -> list[dict]:
    """Load every supported file in a folder (sorted by name, not recursive)."""
    folder = Path(folder)
    if not folder.is_dir():
        raise FileNotFoundError(f"Documents folder not found: {folder}")
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED)
    return [load_document(p, use_transcripts) for p in files]
