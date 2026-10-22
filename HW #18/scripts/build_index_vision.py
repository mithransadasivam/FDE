"""Day 10, Activity 3: rebuild the index, sending scanned pages to the vision model.

    python -m scripts.build_index_vision
    python -m scripts.build_index_vision --folder data/my_docs --name my_docs   (homework)

Like Day 6's build_index, but pages with no text layer are transcribed instead of skipped.
"""

import argparse
from pathlib import Path

import chromadb

from app.embeddings import embed_documents
from app.chunker import chunk_text
from app.indexing import CHROMA_PATH
from app.scanned import load_pages_smart


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default="data/policies")
    ap.add_argument("--name", default="it_policies", help="collection name")
    args = ap.parse_args()
    chroma = chromadb.PersistentClient(path=str(CHROMA_PATH))
    if args.name in [c.name for c in chroma.list_collections()]:
        chroma.delete_collection(args.name)  # rebuild from scratch each time
    # cosine distance, like app/store.py, so the answer code scores chunks the same way
    collection = chroma.create_collection(args.name, metadata={"hnsw:space": "cosine"})
    total, files = 0, 0
    for file in sorted(Path(args.folder).iterdir()):
        if file.suffix.lower() not in (".pdf", ".txt", ".md"):
            continue
        ids, texts, metas, methods = [], [], [], []
        for page, text, method in load_pages_smart(file):
            methods.append(method)
            for i, chunk in enumerate(chunk_text(text)):
                ids.append(f"{file.name}:p{page}:c{i}")
                texts.append(chunk)
                metas.append(
                    {"source": file.name, "page": page, "chunk": i, "method": method}
                )
        if texts:
            collection.add(
                ids=ids,
                documents=texts,
                metadatas=metas,
                embeddings=embed_documents(texts),
            )
        how = ", ".join(
            f"{methods.count(m)} {m}"
            for m in ("text", "vision", "empty")
            if methods.count(m)
        )
        print(f"{len(texts):4} chunks  {file.name}   (pages: {how})")
        total += len(texts)
        files += 1
    print(f"\n{total} chunks from {files} documents stored in collection '{args.name}'")


if __name__ == "__main__":
    main()
