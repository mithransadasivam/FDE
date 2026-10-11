"""Ask the scanned-document questions of the multimodal suite (SCN-*) with the real chatbot and check each answer.

Run: .venv/Scripts/python.exe -m scripts.eval_scans
An answer counts when it is not a decline, cites the scanned file the question belongs to, and contains the key fact (found by the
key words in SCAN_FACTS). Saves data/scan_results.json. Needs the scans to be read and indexed first (build_index --transcribe).
"""
import csv
import json

from app.answer import answer
from app.config import ROOT

SCAN_FACTS = {"SCN-01": ["150"], "SCN-02": ["floor 4"], "SCN-03": ["24 hours"], "SCN-04": ["18:00"], "SCN-05": ["guest network"]}


def main() -> int:
    with open(ROOT / "data" / "multimodal_suite.csv", encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["kind"] == "scan"]
    results = []
    for r in rows:
        result = answer(r["question"])
        cited = sorted({s["source"] for s in result["sources"]})
        read_by_vision = all(s.get("read_by") == "vision" for s in result["sources"] if s["source"] == r["expected_source"])
        facts_ok = all(word in result["answer"].lower() for word in SCAN_FACTS[r["id"]])
        ok = (not result["declined"]) and r["expected_source"] in cited and facts_ok and read_by_vision
        results.append({"id": r["id"], "question": r["question"], "answer": result["answer"], "cited": cited, "ok": ok})
        print(f"{r['id']} {'OK  ' if ok else 'MISS'} cited {cited}")
    answered = sum(1 for x in results if x["ok"])
    (ROOT / "data" / "scan_results.json").write_text(json.dumps({"questions": len(results), "answered": answered, "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"scan questions answered from the scanned file: {answered}/{len(results)}")
    return 0 if answered == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
