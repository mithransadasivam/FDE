"""Ask Spanish, French and German questions of the real chatbot and check each answer.

Run: .venv/Scripts/python.exe -m scripts.eval_languages
For each language: 7 questions the documents answer (the answer must cite the right file, not decline, and be written in the
language of the question), 3 the documents do not cover (must decline, in that language) and 1 unsafe request (must refuse, in that
language). Saves data/language_results.json. Uses the real answer model and the real search, so it costs a few cents.
"""
import json
import time

from app.answer import answer
from app.config import ROOT
from app.language import detect_language
from tests.lang_data import EXPECTED, OUT_OF_SCOPE, QUESTIONS, UNSAFE

PAUSE = 2.0


def main() -> int:
    rows = []
    for language, questions in QUESTIONS.items():
        cases = ([(q, "answer", EXPECTED[i][0]) for i, q in enumerate(questions)] + [(q, "decline", "") for q in OUT_OF_SCOPE[language]]
                 + [(q, "refuse", "") for q in UNSAFE[language]])
        for question, expected, source in cases:
            result = answer(question)
            cited = sorted({s["source"] for s in result["sources"]})
            in_language = detect_language(result["answer"]) == language
            if expected == "answer":
                ok = not result["declined"] and not result["refused"] and source in cited and in_language
            elif expected == "decline":
                ok = result["declined"] and in_language
            else:
                ok = result["refused"] and in_language
            rows.append({"language": language, "expected": expected, "question": question, "ok": ok, "cited": cited, "in_language": in_language,
                         "declined": result["declined"], "refused": result["refused"], "searched_for": result["searched_for"], "answer": result["answer"][:300]})
            print(f"{language} {expected:<7} {'OK  ' if ok else 'MISS'} {question[:56]:<56} -> {result['searched_for'][:50]}", flush=True)
            time.sleep(PAUSE)
    summary = {}
    for language in QUESTIONS:
        mine = [r for r in rows if r["language"] == language]
        summary[language] = {kind: f"{sum(r['ok'] for r in mine if r['expected'] == kind)}/{sum(1 for r in mine if r['expected'] == kind)}" for kind in ("answer", "decline", "refuse")}
    (ROOT / "data" / "language_results.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
