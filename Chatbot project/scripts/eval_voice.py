"""Run every voice note in the multimodal suite through the real speech model and the real chatbot.

Run: .venv/Scripts/python.exe -m scripts.eval_voice
For each note: the transcript, which words differ from what was said, the answer, whether the expected document was cited (or, for the
silent note, whether the user was asked to try again without any call). Saves data/voice_results.json. Costs a few cents.
"""
import csv
import json
import re
import time

from app.answer import answer
from app.config import ROOT
from app.llm import LLMError, call_stt, reset_usage, usage_snapshot
from app.voice import VoiceError, normalise_codes, transcribe
from scripts.make_multimodal_assets import VOICES

SAID = {file: text for file, _, text, _ in VOICES}


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def wrong_words(said: str, heard: str) -> list[str]:
    """Words that were said but not heard, and words heard that were not said (a spelled-out code is compared in its written form)."""
    said_w, heard_w = set(words(normalise_codes(said))), set(words(heard))
    return sorted(said_w ^ heard_w)


def main() -> None:
    with open(ROOT / "data" / "multimodal_suite.csv", encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["kind"] == "voice"]
    results = []
    for r in rows:
        file = r["file"].split("/")[-1]
        data = (ROOT / "data" / "multimodal" / r["file"]).read_bytes()
        reset_usage()
        started = time.time()
        item = {"id": r["id"], "file": file, "said": SAID.get(file, ""), "heard": "", "wrong_words": [], "answer": "", "cited": [], "ok": False, "note": ""}
        try:
            heard = transcribe(data, call_stt)
            item.update(heard=heard["text"], wrong_words=wrong_words(item["said"], heard["text"]), seconds_of_audio=round(heard["seconds"], 1), stt_cost_usd=heard["cost_usd"])
            result = answer(heard["text"])
            item.update(answer=result["answer"], cited=sorted({s["source"] for s in result["sources"]}))
            code_ok = not r["expected_error_code"] or r["expected_error_code"] in heard["text"]
            typed = sorted({s["source"] for s in answer(item["said"])["sources"]})  # the same question typed: the voice path must do no worse
            item.update(typed_cited=typed)
            item["ok"] = code_ok and (r["expected_source"] in item["cited"] or item["cited"] == typed)
            item["note"] = "" if code_ok else "code not written correctly"
        except VoiceError as err:
            item["note"] = f"asked to try again: {err}"
            item["ok"] = r["id"] == "VOC-05" and usage_snapshot().get("stt_calls", 0) == 0  # silence must cost nothing
        except LLMError as err:
            item["note"] = f"model error: {err}"
        item["seconds"] = round(time.time() - started, 1)
        results.append(item)
        print(f"{r['id']} {'OK ' if item['ok'] else 'MISS'} heard: {item['heard']!r} wrong words: {item['wrong_words']} cited: {item['cited']} {item['note']}")
    answered = sum(1 for x in results if x["ok"])
    summary = {"questions": len(results), "answered": answered, "results": results}
    (ROOT / "data" / "voice_results.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"voice notes handled correctly: {answered}/{len(results)}")


if __name__ == "__main__":
    main()
