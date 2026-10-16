"""Tells you when Activity 4 is done: all five tests pass. No model is used."""

from pathlib import Path

from app.triage import Ticket
from app.voice import illustration_prompt, process_voice_note

TICKET = Ticket(error_code="VPN-809", application="SecureLink VPN", summary="The VPN certificate has expired.",
                severity="P3", next_step="Renew the certificate.")


class Recorder:
    def __init__(self, result):
        self.result, self.calls = result, []

    def __call__(self, arg):
        self.calls.append(arg)
        return self.result


def run(tmp_path, transcript="VPN fails with error V P N dash eight zero nine", ticket=TICKET):
    t, k, i = Recorder(transcript), Recorder(ticket), Recorder(b"PNGDATA")
    result = process_voice_note(tmp_path / "note_01.mp3", tmp_path / "out", t, k, i)
    return result, t, k, i


def test_the_chain_runs_in_order_and_returns_everything(tmp_path):
    result, t, k, i = run(tmp_path)
    assert result["file"] == "note_01.mp3"
    assert result["transcript"].startswith("VPN fails")
    assert result["ticket"] == TICKET
    assert k.calls == ["VPN fails with error V P N dash eight zero nine"]


def test_the_illustration_is_saved_as_a_png_named_after_the_note(tmp_path):
    result, *_ = run(tmp_path)
    assert Path(result["image"]) == tmp_path / "out" / "note_01.png"
    assert Path(result["image"]).read_bytes() == b"PNGDATA"


def test_the_image_model_gets_only_the_safe_illustration_prompt(tmp_path):
    _, _, _, i = run(tmp_path)
    assert i.calls == [illustration_prompt(TICKET)]
    assert "VPN-809" not in i.calls[0]


def test_an_empty_transcript_stops_the_chain(tmp_path):
    result, _, k, i = run(tmp_path, transcript="   ")
    assert result == {"file": "note_01.mp3", "transcript": "", "ticket": None, "image": None}
    assert k.calls == [] and i.calls == []


def test_no_ticket_means_no_illustration(tmp_path):
    result, _, _, i = run(tmp_path, ticket=None)
    assert result["ticket"] is None and result["image"] is None
    assert i.calls == []
    assert not (tmp_path / "out").exists()
