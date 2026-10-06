"""Day 7 names for the Day 6 index code: the vector store location, collection access and page loading."""
from pathlib import Path

from app.config import CHROMA_DIR
from app.loader import load_document
from app.store import get_collection as _get_collection

CHROMA_PATH = CHROMA_DIR


def get_collection(name: str = "my_docs", path=CHROMA_PATH):
    """Day 7 order is (name, path); Day 6's store uses (path, name)."""
    return _get_collection(path, name)


def load_pages(file) -> list[tuple[int, str]]:
    """[(page number, text)] for one .pdf, .md or .txt file."""
    return load_document(Path(file))["pages"]
