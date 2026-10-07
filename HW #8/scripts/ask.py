"""Ask one question from the command line (uses the real answer model).

Run: .venv/Scripts/python.exe -m scripts.ask "How long do you keep daily server backups?"
"""
import sys

from app.answer import answer
from app.embeddings import EmbeddingError
from app.llm import LLMError


def main() -> int:
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        print('Usage: python -m scripts.ask "your question"')
        return 1
    try:
        result = answer(question)
    except (ValueError, EmbeddingError, LLMError) as err:
        print(f"ERROR: {err}")
        return 1
    print(f"Q: {question}")
    print(f"A: {result['answer']}")
    print(f"declined: {result['declined']}  ({result['reason'] or 'answered'})")
    print(f"best score {result['best_score']}, chunks used {result['chunks_used']}, {result['seconds']}s")
    for s in result["sources"]:
        print(f"  [{s['number']}] {s['source']} · page {s['page']} (score {s['score']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
