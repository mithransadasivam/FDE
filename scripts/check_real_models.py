"""Checks that the platform can use REAL models (the switch from fake mode). Makes one tiny call to each model; costs a fraction of a cent.

    python -m scripts.check_real_models          (set FAKE_MODELS=0 and OPENROUTER_API_KEY in .env first)

What it checks: every model in the router (small, large, local, fallback) and the vision model answer a one-word prompt; faster-whisper loads and
transcribes one recorded answer; the text-to-speech engine can speak. Each line says OK or FIX with what to do.
"""
import sys
import time
from pathlib import Path

from app.config import get_settings

OK, FIX = "OK  ", "FIX "


def line(ok: bool, label: str, detail: str = "") -> bool:
    print(f"{OK if ok else FIX} {label}" + (f": {detail}" if detail else ""))
    return ok


def call(model: str, key: str) -> tuple[bool, str]:
    try:
        import litellm
        t = time.perf_counter()
        r = litellm.completion(model=model, messages=[{"role": "user", "content": "Reply with the single word: ready"}], max_tokens=5, temperature=0,
                               api_key=key or None, timeout=60)
        return True, f"{r.choices[0].message.content.strip()[:20]!r} in {time.perf_counter() - t:.1f}s"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:140]}"


def main() -> int:
    s = get_settings()
    results = []
    results.append(line(not s.fake_models, "FAKE_MODELS is off", "set FAKE_MODELS=0 in .env to use real models" if s.fake_models else ""))
    results.append(line(bool(s.openrouter_api_key), "OPENROUTER_API_KEY is set", "add it to .env (never commit .env)" if not s.openrouter_api_key else ""))
    if s.openrouter_api_key:
        for tier, model in (("small (extraction, point-ticking)", s.small_model), ("large (scoring, suggestions)", s.large_model), ("fallback", s.fallback_model),
                            ("vision (scanned CVs)", s.vision_model)):
            ok, detail = call(model, s.openrouter_api_key)
            results.append(line(ok, f"{tier} model {model}", detail))
        if s.local_model.startswith("ollama/"):
            ok, detail = call(s.local_model, "")
            results.append(line(ok, f"local model {s.local_model} (used for steps that see identity)", detail if not ok else detail + "; install Ollama and `ollama pull " + s.local_model.split('/')[1] + "` if this fails"))
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(s.whisper_model, device="cpu", compute_type="int8")
        clip = next(Path(s.kit_dir, "recorded_answers").glob("A-001.wav"))
        text = " ".join(x.text for x in model.transcribe(str(clip), language="en")[0]).strip()
        results.append(line(bool(text), f"speech to text (faster-whisper {s.whisper_model})", text[:60]))
    except Exception as e:
        results.append(line(False, "speech to text (faster-whisper)", f"{type(e).__name__}: {str(e)[:100]}"))
    try:
        import pyttsx3
        pyttsx3.init()
        results.append(line(True, "text to speech (pyttsx3, the system voices)"))
    except Exception as e:
        results.append(line(False, "text to speech", f"{type(e).__name__}; the interview page falls back to the browser's voice"))
    print("\nReady to use real models." if all(results) else "\nSome things need fixing before real models will work (see FIX lines). Fake mode still works.")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
