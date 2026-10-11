"""What each kind of multimodal input costs, in tokens, dollars and image size.

Run: .venv/Scripts/python.exe -m scripts.benchmark_multimodal
Uses the numbers saved by the earlier runs (screenshot_results.json, ticket_scores.json, voice_results.json) and measures one scanned page
for real. Prices come from .env (vision uses the same model and price as the answer model; speech and pictures use the rough prices in
app/config.py). Saves data/multimodal_costs.json and adds a "multimodal" entry to data/eval_summary.json.
"""
import json
import os
from statistics import mean

from dotenv import load_dotenv

from app.benchmark import cost_usd
from app.config import IMAGE_COST_USD, ROOT, STT_PRICE_PER_MINUTE
from app.eval_suite import update_summary
from app.llm import reset_usage, usage_snapshot
from app.scanned import transcribe_page

DATA = ROOT / "data"


def load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def main() -> int:
    load_dotenv(ROOT / ".env")
    price_in, price_out = float(os.environ["INPUT_PRICE"]), float(os.environ["OUTPUT_PRICE"])
    shots = load("screenshot_results.json")["rows"]
    tickets = [r for r in load("ticket_scores.json")["results"] if "ticket" in r]
    voice = [r for r in load("voice_results.json")["results"] if r.get("seconds_of_audio")]

    screenshot_costs = [cost_usd(r["vision_input_tokens"] + r["answer_input_tokens"], r["vision_output_tokens"] + r["answer_output_tokens"], price_in, price_out) for r in shots]
    ticket_costs = [cost_usd(r["vision_input_tokens"], r["vision_output_tokens"], price_in, price_out) for r in tickets]
    pdf = next((DATA / "docs").glob("printing_policy_scanned.pdf"))
    reset_usage()
    transcribe_page(pdf, 1)
    usage = usage_snapshot()
    page_cost = cost_usd(usage["vision_input_tokens"], usage["vision_output_tokens"], price_in, price_out)

    result = {
        "prices_per_million_tokens": {"input": price_in, "output": price_out},
        "screenshot_question": {"n": len(shots), "image_sent": "longest side 1024 px", "avg_vision_tokens_in": round(mean(r["vision_input_tokens"] for r in shots)),
                                "avg_answer_tokens_in": round(mean(r["answer_input_tokens"] for r in shots)), "avg_bytes_sent": round(mean(r["image_info"]["bytes_sent"] for r in shots)),
                                "avg_cost_usd": round(mean(screenshot_costs), 5), "cost_per_1000_usd": round(mean(screenshot_costs) * 1000, 2)},
        "ticket": {"n": len(tickets), "avg_vision_tokens_in": round(mean(r["vision_input_tokens"] for r in tickets)), "avg_cost_usd": round(mean(ticket_costs), 5),
                   "cost_per_1000_usd": round(mean(ticket_costs) * 1000, 2)},
        "scanned_page_read": {"vision_tokens_in": usage["vision_input_tokens"], "vision_tokens_out": usage["vision_output_tokens"], "cost_usd": round(page_cost, 5),
                              "note": "paid once per page: the text is saved and re-indexing costs nothing"},
        "voice_question": {"n": len(voice), "avg_audio_seconds": round(mean(r["seconds_of_audio"] for r in voice), 1), "avg_speech_cost_usd": round(mean(r["stt_cost_usd"] for r in voice), 5),
                           "price_per_minute_usd": STT_PRICE_PER_MINUTE},
        "picture_out": {"cost_usd": IMAGE_COST_USD, "note": "off by default; one picture per button press"},
    }
    (DATA / "multimodal_costs.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    update_summary({"multimodal": result})
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
