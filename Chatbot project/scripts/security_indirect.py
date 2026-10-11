"""Indirect injection: index one poisoned document in a SEPARATE test collection and ask the chatbot about it.

Run: .venv/Scripts/python.exe -m scripts.security_indirect
The poisoned file (data/security_tests/poisoned_vpn_note.md) is never put in data/docs or the real collection.
Passes when the chatbot answers the real question from it and the code word never appears.
Saves data/security_indirect.json and adds the result to data/eval_summary.json.
"""
import json

from app.answer import answer
from app.chunker import chunk_document
from app.config import DOCS_DIR
from app.embeddings import EmbeddingError, embed_documents
from app.eval_suite import update_summary
from app.llm import LLMError
from app.loader import load_documents
from app.retriever import search
from app.security_check import (POISONED_DIR, QUESTION, ROOT, TEST_CHROMA_DIR, TEST_COLLECTION, evaluate_indirect,
                                poisoned_file_is_kept_out_of_the_real_knowledge_base)
from app.store import build_index


def main() -> int:
    if not poisoned_file_is_kept_out_of_the_real_knowledge_base():
        print(f"ERROR: the poisoned file must not be in {DOCS_DIR}. Remove it.")
        return 1
    try:
        chunks = [c for doc in load_documents(POISONED_DIR) for c in chunk_document(doc)]
        total = build_index(chunks, embed_documents, TEST_CHROMA_DIR, TEST_COLLECTION)
        print(f"Indexed {total} chunks of the poisoned note in the test collection '{TEST_COLLECTION}' (not the real one).")
        result = answer(QUESTION, retriever=lambda q, k: search(q, k, path=TEST_CHROMA_DIR, name=TEST_COLLECTION))
    except (ValueError, EmbeddingError, LLMError) as err:
        print(f"ERROR: {err}")
        return 1

    verdict = evaluate_indirect(result)
    print(f"Question: {QUESTION}\nAnswer:   {result['answer']}\n")
    print(f"leaked the code word: {verdict['leaked']}  |  answered the real question: {verdict['answered_normally']}  |  "
          f"output guard had to step in: {verdict['guard_blocked']}")
    print("PASS" if verdict["passed"] else "FAIL")
    (ROOT / "data" / "security_indirect.json").write_text(json.dumps({"question": QUESTION, **verdict}, indent=2), encoding="utf-8")
    update_summary({"security": {"indirect_injection": "pass" if verdict["passed"] else "fail"}})
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
