"""Accent test (Day 4, prompt 3): does the way an answer SOUNDS change its transcript, and so its level? That would be unfair (rule 4: content, not tone).

6 answers (2 strong, 2 partial, 2 weak) come from the sample interviews. Each is spoken by neural computer voices with different English accents
(British, Scottish, Irish-influenced, US) plus one slow and one fast version. Every recording is transcribed with the REAL Whisper model, the word
error rate is measured against the original text, and the transcript is scored with the interviewer's scorer (score_text) against the same
question and scale. Pass: no answer's level differs by more than 1 between voices.

This test cannot be faked: transcription is what it tests. It stops with a clear message if the speech model or the voices are not available.
(Whisper runs locally, so it needs no key even when FAKE_MODELS=1; only the SCORING follows FAKE_MODELS, and the report says which it was.)

    python -m evals.accent_test           (all voices, 6 answers: several minutes)
    python -m evals.accent_test --quick   (3 answers, 3 voices: for class)
Writes reports/accent_test.md and reports/accent_test.json; the recordings are kept in reports/accent_audio/ (not committed).

Limit, said plainly: these are computer voices. They do not represent real people's accents well. The test can show a problem; passing it does not
prove there is none. Real accented speech from real speakers is still needed.
"""
import argparse
import glob
import re
import sys
import wave
from pathlib import Path

from sqlalchemy import select

from app.agents.interviewer import score_text
from app.ai.voice import transcribe_real
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.interview.bank import load_questions
from app.models_ext import InterviewSession
from evals.common import REPORTS, run_info, table, write_report

MAX_LEVEL_DIFFERENCE = 1
AUDIO = REPORTS / "accent_audio"
# (file stem, label, length_scale): length_scale below 1 is faster, above 1 slower
VOICES = [("en_GB-alan-medium", "British English (alan)", None), ("en_GB-alba-medium", "Scottish English (alba)", None),
          ("en_GB-jenny_dioco-medium", "Irish-influenced English (jenny_dioco)", None), ("en_US-lessac-medium", "US English (lessac)", None),
          ("en_US-ryan-medium", "US English (ryan)", None), ("en_US-lessac-medium", "US English, slow (lessac x1.5)", 1.5),
          ("en_US-lessac-medium", "US English, fast (lessac x0.65)", 0.65)]
QUICK_VOICES = [VOICES[0], VOICES[1], VOICES[5]]


class NotAvailable(Exception):
    pass


def voice_path(stem: str) -> Path:
    lang = stem.split("-")[0]
    name = stem.split("-")[1]
    hits = glob.glob(str(Path.home() / ".cache/huggingface/hub/models--rhasspy--piper-voices/snapshots/*/en" / lang / name / "medium" / f"{stem}.onnx"))
    extra = Path(get_settings().__dict__.get("piper_dir", "")) / f"{stem}.onnx" if get_settings().__dict__.get("piper_dir") else None
    if extra and extra.exists():
        return extra
    if not hits:
        raise NotAvailable(f"The voice {stem} is not installed (look in ~/.cache/huggingface/hub/models--rhasspy--piper-voices).")
    return Path(hits[0])


def speak(text: str, out: Path, stem: str, length_scale: float | None) -> None:
    from piper import PiperVoice, SynthesisConfig

    voice = PiperVoice.load(str(voice_path(stem)))
    with wave.open(str(out), "wb") as w:
        voice.synthesize_wav(text, w, syn_config=SynthesisConfig(length_scale=length_scale) if length_scale else None)


def check_ready(voices: list) -> None:
    """Stop with a clear message if the real speech model or the voices are missing."""
    try:
        from app.ai.voice import whisper_model

        whisper_model()
    except Exception as e:
        raise NotAvailable(f"The accent test needs the real Whisper model ({get_settings().whisper_model}) and cannot be faked, because transcription is what it tests. "
                           f"It could not be loaded: {e}. Run python -m scripts.check_setup.") from e
    try:
        import piper  # noqa: F401
    except Exception as e:
        raise NotAvailable("The accent test needs piper-tts for the accented voices: pip install piper-tts") from e
    for stem, _l, _s in voices:
        voice_path(stem)


def wer(ref: str, hyp: str) -> float:
    r = re.sub(r"[^a-z0-9 ]", "", ref.lower()).split()
    h = re.sub(r"[^a-z0-9 ]", "", hyp.lower()).split()
    d = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        prev, d[0] = d[0], i
        for j, hw in enumerate(h, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (rw != hw))
    return round(d[len(h)] / max(1, len(r)), 4)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def pick_answers(bank: dict, how_many: int) -> list[dict]:
    """2 strong, 2 partial, 2 weak answers from the sample interviews. Strong and weak are used as spoken in the interviews; a partial answer is a strong
    answer cut after its first sentences until the scorer gives it 1 or 2 (so every level of the scale is tested)."""
    init_db()
    strong, weak = [], []
    with SessionLocal() as db:
        for s in db.scalars(select(InterviewSession).where(InterviewSession.sample.is_(True), InterviewSession.status == "DONE").order_by(InterviewSession.id)):
            for t in (s.state or {}).get("turns", []):
                q = bank.get(t.get("question_id"))
                if not q or t.get("opening") or t.get("skipped") or not t.get("answers") or q["type"] != "technical":
                    continue
                text = t["answers"][0]["text"]
                words = len(text.split())
                if words < 5:
                    continue
                level = score_text(q, text).score
                row = {"question_id": q["id"], "skill": q["skill"], "text": text, "source": f"sample interview {s.id}"}
                (strong if level == 3 and words >= 20 else weak if level == 0 else []).append({**row, "baseline": level})
    out, used = [], set()

    def take(pool, n):
        for r in pool:
            if len([o for o in out if o["bucket"] == pool_name]) >= n:
                break
            if r["question_id"] in used:
                continue
            used.add(r["question_id"])
            out.append({**r, "bucket": pool_name})

    per = max(1, how_many // 3)
    pool_name = "strong"
    take(strong, per)
    pool_name = "weak"
    take(weak, per)
    partial = []
    for r in strong[::-1]:
        if r["question_id"] in used:
            continue
        sents = _sentences(r["text"])
        for k in range(1, len(sents)):
            cut = " ".join(sents[:k])
            lv = score_text(bank[r["question_id"]], cut).score
            if lv in (1, 2):
                partial.append({**r, "text": cut, "baseline": lv, "source": f"{r['source']}, cut to its first {k} sentence(s)", "bucket": "partial"})
                break
    for r in partial[:per]:
        used.add(r["question_id"])
        out.append(r)
    return out


def main(quick: bool = False) -> int:
    voices = QUICK_VOICES if quick else VOICES
    how_many = 3 if quick else 6
    try:
        check_ready(voices)
    except NotAvailable as e:
        print("STOPPED:", e)
        return 3
    bank = load_questions()
    answers = pick_answers(bank, how_many)
    if len(answers) < how_many:
        print(f"STOPPED: only {len(answers)} suitable answers were found in the sample interviews. Run python -m scripts.make_sample_interviews first.")
        return 3
    AUDIO.mkdir(parents=True, exist_ok=True)
    results = []
    for a_i, a in enumerate(answers):
        q = bank[a["question_id"]]
        per_voice = []
        for v_i, (stem, label, scale) in enumerate(voices):
            wav = AUDIO / f"answer{a_i + 1}_{a['bucket']}_{'slow' if scale and scale > 1 else 'fast' if scale else 'normal'}_{stem}.wav"
            speak(a["text"], wav, stem, scale)
            heard = transcribe_real(wav)
            sc = score_text(q, heard)
            per_voice.append({"voice": label, "file": str(wav), "wer": wer(a["text"], heard), "level": sc.score, "transcript": heard})
        levels = [p["level"] for p in per_voice]
        results.append({"answer": a_i + 1, "bucket": a["bucket"], "question_id": a["question_id"], "skill": a["skill"], "source": a["source"], "text": a["text"],
                        "level_from_text": a["baseline"], "per_voice": per_voice, "largest_level_difference": max(levels) - min(levels),
                        "difference_from_text_level": max(abs(l - a["baseline"]) for l in levels)})
        print(f"  answer {a_i + 1}/{len(answers)} ({a['bucket']}, {a['question_id']}): levels {levels}, WER {[p['wer'] for p in per_voice]}")
    by_voice = {}
    for r in results:
        for p in r["per_voice"]:
            by_voice.setdefault(p["voice"], []).append(p["wer"])
    wer_by_voice = {k: round(sum(v) / len(v), 4) for k, v in by_voice.items()}
    worst = max(wer_by_voice, key=wer_by_voice.get)
    worst_rec = max((p for r in results for p in r["per_voice"]), key=lambda p: p["wer"])
    largest = max(r["largest_level_difference"] for r in results)
    passed = largest <= MAX_LEVEL_DIFFERENCE
    md = ["## Pass rule", f"No answer's level may differ by more than {MAX_LEVEL_DIFFERENCE} between voices. Largest difference: **{largest}**.", "",
          "## Word error rate by voice (mean over the answers)", table(["voice", "mean WER"], [[k, f"{v:.1%}"] for k, v in wer_by_voice.items()]),
          f"\nHighest mean error rate: **{worst}** ({wer_by_voice[worst]:.1%}). Highest single recording: `{worst_rec['file']}` ({worst_rec['wer']:.1%}).", "",
          "## Level per voice, for each answer", table(["answer", "kind", "skill", "level from the text"] + [v[1] for v in voices] + ["largest difference"],
                                                    [[r["answer"], r["bucket"], r["skill"], r["level_from_text"]] + [p["level"] for p in r["per_voice"]] + [r["largest_level_difference"]] for r in results]), "",
          "## The answers", *[f"{r['answer']}. **{r['bucket']}**, {r['question_id']} ({r['source']}): {r['text'][:160]}..." for r in results], "",
          "## Limits", "- These are computer voices. They do not represent real people's accents well: passing this test does not prove there is no problem with real speakers.",
          f"- Scoring ran in {'fake (rule-based keyword) mode' if get_settings().fake_models else 'real-model mode'}: with the rule-based scorer a mis-heard keyword can lower a level, which is what this test would show; "
          "a language model may be more or less forgiving. Run it again with real models.", "- Only a few answers and voices were used.", ""]
    write_report("accent_test", "Accent test", {"answers": len(answers), "voices": [v[1] for v in voices], "max_level_difference": MAX_LEVEL_DIFFERENCE,
                                                  "whisper_model": get_settings().whisper_model, "scoring": "fake (rule-based)" if get_settings().fake_models else "real", "quick": quick},
                 {"wer_by_voice": wer_by_voice, "largest_level_difference": largest, "highest_wer_recording": worst_rec["file"], "answers": results}, passed, "\n".join(md))
    print(f"Accent test: {len(answers)} answers x {len(voices)} voices; largest level difference {largest}; highest mean WER {worst} {wer_by_voice[worst]:.1%}; {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 2


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    sys.exit(main(ap.parse_args().quick))
