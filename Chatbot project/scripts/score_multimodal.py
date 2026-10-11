"""Collect the multimodal numbers from the saved runs into the evaluation summary, where the gate reads them.

Run: .venv/Scripts/python.exe -m scripts.score_multimodal        (no model calls: it only reads data/*.json)
Needs the earlier runs: eval_screenshots, score_tickets, eval_voice, eval_scans, benchmark_multimodal.
"""
import json

from app.config import ROOT
from app.eval_suite import update_summary

FIELDS = ("error_code", "application", "severity", "summary", "next_step")


def load(name: str) -> dict:
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def main() -> int:
    shots, tickets, voice, scans = load("screenshot_results.json"), load("ticket_scores.json"), load("voice_results.json"), load("scan_results.json")
    made = [r for r in tickets["results"] if "ticket" in r]
    right = sum(sum(1 for f in FIELDS if r["scores"][f]) for r in made)
    injection = [r for r in shots["rows"] if "injection" in r["file"]]
    numbers = {
        "screenshot_pass_rate": round(shots["passed"] / shots["total"], 3),
        "ticket_field_accuracy": round(right / (len(tickets["results"]) * len(FIELDS)), 3),
        "ticket_code_accuracy": round(tickets["right"]["error_code"] / len(tickets["results"]), 3),
        "voice_answered": round(voice["answered"] / voice["questions"], 3),
        "scan_answered": round(scans["answered"] / scans["questions"], 3),
        "injection_resisted": round(sum(1 for r in injection if r["passed"]) / len(injection), 3),
        "largest_image_tokens": max(r["vision_input_tokens"] for r in shots["rows"] + made),
        "counts": {"screenshots": shots["total"], "tickets": len(tickets["results"]), "voice": voice["questions"], "scans": scans["questions"], "injection_images": len(injection)},
    }
    update_summary({"multimodal": numbers})
    print(json.dumps(numbers, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
