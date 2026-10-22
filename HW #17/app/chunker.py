"""Cut text into overlapping chunks that remember their file and page."""
from app.config import CHUNK_OVERLAP, CHUNK_SIZE


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into chunks of at most `size` characters.

    Each chunk starts `size - overlap` characters after the previous one, so
    neighbouring chunks share `overlap` characters. Empty or whitespace-only
    text gives an empty list.
    """
    if size <= 0:
        raise ValueError("size must be greater than 0")
    if overlap < 0:
        raise ValueError("overlap must not be negative")
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")

    text = text.strip()
    if not text:
        return []

    step = size - overlap
    chunks = []
    start = 0
    while start < len(text):
        piece = text[start:start + size].strip()
        if piece:
            chunks.append(piece)
        if start + size >= len(text):
            break
        start += step
    return chunks


def chunk_document(doc, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """Chunk every page of a loaded document.

    Returns dicts with: source, page, chunk (1-based number within the file), text.
    """
    chunks = []
    number = 0
    for page, text in doc["pages"]:
        for piece in chunk_text(text, size, overlap):
            number += 1
            chunks.append({"source": doc["source"], "page": page, "chunk": number, "text": piece})
    return chunks
