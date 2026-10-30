"""Cost and speed report (Day 4, prompt 5): writes reports/cost_and_speed.md and .json with the same numbers as the Trust and cost page.

    python -m scripts.cost_report             the numbers from the calls logged so far (the app's own database)
    python -m scripts.cost_report --measure   ALSO runs a clean measured run in a scratch folder (the 52 CVs, three sample interviews with a real voice), and
                                              measures one improvement before and after: reusing the recording of a fixed question instead of speaking it again

Everything comes from the ModelCall and ResponseTiming logs. Fake mode has no real model cost: the cost shown is what the same tokens would cost at the list prices
(app/ai/router.py), and the report says so. Transcription and text-to-speech run on this machine, cost nothing and are timed.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from app import costing
from evals.common import table, write_report

SCRATCH_ENV = ("DATABASE_URL", "OPS_DATABASE_URL", "STORAGE_DIR")


def measure_speech_cache() -> dict:
    """The improvement: a fixed question (the question guide's own wording) is spoken once and the recording reused for every later candidate.
    Measured the same way before and after: the seconds the voice needs for the 8 core questions of ONE interview (the second candidate's, so the cache is
    warm in the 'after' case). A real voice is used; if none is available this says so."""
    import shutil
    import time

    from app.ai import speech
    from app.config import get_settings
    from app.interview.bank import load_questions

    texts = [q["question"] for q in list(load_questions().values())[:8]]
    out = Path(tempfile.mkdtemp(prefix="speech_cache_"))
    s = get_settings()

    def one_interview(label: str) -> float:
        started = time.perf_counter()
        for i, t in enumerate(texts):
            if speech.speak(t, out / f"{label}_{i}.wav", real=True) is None:
                raise RuntimeError("no real voice available")
        return time.perf_counter() - started

    try:
        s.speech_cache = False
        before_first, before_second = one_interview("b1"), one_interview("b2")  # cache off: every candidate pays the full price
        s.speech_cache = True
        shutil.rmtree(s.storage_dir / "tts_cache", ignore_errors=True)
        after_first, after_second = one_interview("a1"), one_interview("a2")  # cache on: the first candidate fills it, the second reuses it
    except RuntimeError as e:
        return {"measured": False, "why": str(e)}
    finally:
        s.speech_cache = True
        shutil.rmtree(out, ignore_errors=True)
    return {"measured": True, "questions": len(texts), "before_s": round(before_second, 3), "after_s": round(after_second, 3),
            "first_candidate_after_s": round(after_first, 3), "saved_s": round(before_second - after_second, 3),
            "improvement_pct": round(100 * (before_second - after_second) / before_second, 1) if before_second else 0.0,
            "voice": "operating-system voice (pyttsx3)"}


def inner() -> int:
    """Runs inside the scratch folder (the environment points the databases there)."""
    for mod in ("scripts.day1_demo", "scripts.make_sample_interviews"):
        done = subprocess.run([sys.executable, "-m", mod], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if done.returncode != 0:
            print(f"{mod} failed", file=sys.stderr)
            return 1
    from app.db import SessionLocal
    from app.models import Candidate
    from app.practice import load_practice
    from evals import copilot_eval

    with SessionLocal() as db:  # two copilot sessions on practice interviews, so a copilot session has a cost
        for cid in copilot_eval.ensure_practice(db)[:2]:
            copilot_eval.run_copilot(db, db.get(Candidate, cid), load_practice(cid), 0.0)
    result = {"cost": costing.cost_numbers(), "speed": costing.speed_numbers(), "speech_cache": measure_speech_cache()}
    Path(os.environ["MEASURE_OUT"]).write_text(json.dumps(result), encoding="utf-8")
    return 0


def measured_run() -> dict | None:
    scratch = Path(tempfile.mkdtemp(prefix="cost_measure_"))
    env = dict(os.environ, FAKE_MODELS="1", DATABASE_URL=f"sqlite:///{(scratch / 'a.db').as_posix()}", OPS_DATABASE_URL=f"sqlite:///{(scratch / 'o.db').as_posix()}",
               STORAGE_DIR=str(scratch / "storage"), MEASURE_OUT=str(scratch / "out.json"))
    print("Measured run in a scratch folder (52 CVs, 3 sample interviews with a real voice; about a minute or two) ...")
    done = subprocess.run([sys.executable, "-m", "scripts.cost_report", "--inner"], env=env)
    out = scratch / "out.json"
    result = json.loads(out.read_text(encoding="utf-8")) if done.returncode == 0 and out.exists() else None
    import shutil

    shutil.rmtree(scratch, ignore_errors=True)
    return result


def money(v) -> str:
    return "n/a" if v is None else f"${v:.4f}"


def main(measure: bool) -> int:
    live = {"cost": costing.cost_numbers(), "speed": costing.speed_numbers()}
    run = measured_run() if measure else None
    source = run or live
    c, sp = source["cost"], source["speed"]
    cache = (run or {}).get("speech_cache")
    md = ["## Cost, from the logged model calls" + (" (measured run)" if run else ""),
          table(["what", "cost", "based on"], [["per CV read", money(c["per_cv_read"]["per_unit"]), f"{c['per_cv_read']['units']} CVs"],
                                                ["per CV screened and checked", money(c["per_cv_screened"]["per_unit"]), f"{c['per_cv_screened']['units']} CVs"],
                                                ["**per 100 CVs**", money(c["per_100_cvs"]), "read + screened + checked"],
                                                ["per AI interview", money(c["per_interview"]["per_unit"]), f"{c['per_interview']['units']} interviews"],
                                                ["per copilot session", money(c["per_copilot_session"]["per_unit"]), f"{c['per_copilot_session']['units']} sessions"]]), "",
          ("**Fake mode:** no model was called. These are the costs the same tokens would have at the list prices in app/ai/router.py." if c["simulated"]
           else "Costs are the provider's own price for each call (LiteLLM)."), "",
          "### Cost by agent", table(["agent", "calls", "cached", "tokens", "cost", "seconds"],
                                     [[a, v["calls"], v["cached"], v["tokens"], money(v["cost"]), v["seconds"]] for a, v in c["by_agent"].items()]), ""]
    if c["per_100_cvs"] is not None:
        per_month = c["per_100_cvs"] * 10
        iv = c["per_interview"]["per_unit"] or 0.0
        md += ["### What 1,000 applications a month would cost, from these numbers",
               f"CV reading, screening and checking: about **{money(per_month)}**. If 10% are interviewed by the AI: add about **{money(iv * 100)}** (100 interviews x {money(iv)}). "
               f"Add {money((c['per_copilot_session']['per_unit'] or 0.0) * 30)} if 30 of them also get a copilot session. "
               "These use list prices and a fake-model run; the real number needs a real-model run.", ""]
    md += ["## How fast the interviewer replies"]
    if sp["answers"]:
        md += [f"Seconds from the candidate's answer to the next question being playable ({sp['answers']} answers" + ("; model calls were fake, so scoring/question/diagram show compute only" if sp["simulated"] else "") + ").",
               table(["step", "median (s)", "slowest (s)"], [[k, v["median"], v["slowest"]] for k, v in sp["steps"].items()] +
                     [["**whole reply**", sp["total"]["median"], sp["total"]["slowest"]]]),
               f"\nSlowest step by median: **{sp['slowest_step_overall']}**. Slowest single answer: candidate {sp['slowest_answer']['candidate']}, question {sp['slowest_answer']['turn']} ({sp['slowest_answer']['total_s']} s).", ""]
    else:
        md += ["No interview answers have been timed yet: run an interview (or `python -m scripts.cost_report --measure`).", ""]
    wt = costing.copilot_warning_times()
    md += ["## Copilot warning time", (f"From reports/copilot_eval.json ({wt['date']}): average **{wt['average_s']} s**, slowest **{wt['slowest_s']} s** after a forbidden question ended."
                                       if wt else "Not measured yet: run `python -m evals.copilot_eval`."), ""]
    md += ["## One improvement, measured before and after"]
    if cache and cache.get("measured"):
        md += ["**Reuse the recording of a fixed question instead of speaking it again.** The 8 core questions are the same for every candidate, so the voice only needs to speak them once. "
               "Written questions mention the CV, so they are never cached.",
               table(["", "seconds of speech for one interview's 8 core questions"], [["before (cache off, every candidate)", cache["before_s"]], ["after (cache on, second candidate)", cache["after_s"]],
                                                                                       ["after, first candidate (fills the cache)", cache["first_candidate_after_s"]]]),
               f"\nSaved **{cache['saved_s']} s per interview ({cache['improvement_pct']}%)**, measured the same way both times with a real voice ({cache['voice']}). The first candidate pays full price once.", ""]
    else:
        md += [("Not measured in this run: " + cache["why"]) if cache else "Run `python -m scripts.cost_report --measure` to measure it (needs a real voice).", ""]
    md += ["## Limits", "- Fake mode: model cost is what the tokens would cost at list prices, and model time is only the platform's compute. A real-model run gives real cost and time.",
           "- Speech and transcription times are measured only when a real voice or Whisper ran; fake mode writes a short silent file.", ""]
    results = {"cost": c, "speed": sp, "speech_cache": cache, "copilot_warning": wt, "measured_run": bool(run)}
    write_report("cost_and_speed", "Cost and speed", {"measured_run": bool(run)}, results, True, "\n".join(md))
    print(f"Cost and speed: per 100 CVs {money(c['per_100_cvs'])}, per interview {money(c['per_interview']['per_unit'])}, per copilot session {money(c['per_copilot_session']['per_unit'])}; "
          f"{sp['answers']} answers timed" + (f"; speech cache saves {cache['saved_s']} s ({cache['improvement_pct']}%)" if cache and cache.get('measured') else ""))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--inner", action="store_true")
    a = ap.parse_args()
    sys.exit(inner() if a.inner else main(a.measure))
