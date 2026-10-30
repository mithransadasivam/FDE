"""Day 4 prompt 3: the accent test: real transcription, word error rate, a level per voice, and a clear stop when the speech model is missing."""
import pytest

from app.agents.interviewer import score_text
from app.ai.voice import transcribe_real
from app.interview.bank import load_questions
from evals import accent_test as at
from evals.common import load_report


def test_word_error_rate_counts_wrong_missing_and_extra_words():
    assert at.wer("the cat sat", "the cat sat") == 0.0
    assert at.wer("the cat sat", "the dog sat") == round(1 / 3, 4)
    assert at.wer("the cat sat", "the cat") == round(1 / 3, 4)
    assert at.wer("one two", "one two three four") == 1.0


def test_the_test_stops_with_a_clear_message_when_whisper_is_missing(monkeypatch, capsys):
    import app.ai.voice as voice

    def broken():
        raise RuntimeError("model files not found")

    monkeypatch.setattr(voice, "whisper_model", broken)
    assert at.main(quick=True) == 3
    out = capsys.readouterr().out
    assert "cannot be faked" in out and "model files not found" in out


def test_the_voices_for_the_accents_are_installed():
    for stem, _label, _scale in at.VOICES:
        assert at.voice_path(stem).exists()
    assert len({v[0] for v in at.VOICES}) >= 4 and any(v[2] and v[2] > 1 for v in at.VOICES) and any(v[2] and v[2] < 1 for v in at.VOICES)  # 4+ voices, one slow, one fast


def test_one_answer_spoken_two_ways_is_really_transcribed_and_scored(tmp_path):
    q = load_questions()["T-06"]
    text = "I acknowledge the alert and assess who is affected. I communicate early and open an incident channel. I mitigate first, for example by rolling back."
    levels, wers = [], []
    for stem, scale in (("en_GB-alba-medium", None), ("en_US-lessac-medium", 1.5)):
        wav = tmp_path / f"{stem}.wav"
        at.speak(text, wav, stem, scale)
        heard = transcribe_real(wav)  # the real Whisper model, even when FAKE_MODELS=1
        assert heard and heard != text or heard == text
        wers.append(at.wer(text, heard))
        levels.append(score_text(q, heard).score)
    assert max(wers) < 0.5 and max(levels) - min(levels) <= at.MAX_LEVEL_DIFFERENCE


def test_the_report_is_dated_and_says_what_it_used():
    doc = load_report("accent_test")
    if doc is None:
        pytest.skip("run python -m evals.accent_test first")
    assert doc["date"] and doc["settings"]["whisper_model"] and doc["settings"]["scoring"] and "wer_by_voice" in doc["results"]
    assert "computer voices" in open("reports/accent_test.md", encoding="utf-8").read()
