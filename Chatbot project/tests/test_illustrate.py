"""Pictures out: off by default, only a one-sentence summary is sent, the picture is labelled, and a bad picture is not shown."""
import pytest

from app.config import ILLUSTRATION_STYLE, ILLUSTRATION_SUMMARY_CHARS, ILLUSTRATIONS_ENABLED, IMAGE_COST_USD
from app.fake_chat import fake_draw
from app.illustrate import LABEL, IllustrationError, illustrate, prompt_for, summary_of
from app.llm import LLMError


class Drawer:
    def __init__(self, picture=None, fail=False):
        self.picture, self.fail, self.prompts = fake_draw("") if picture is None else picture, fail, []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if self.fail:
            raise LLMError("down")
        return self.picture


def test_pictures_are_off_unless_switched_on():
    assert ILLUSTRATIONS_ENABLED is False


def test_when_off_nothing_is_built_and_no_picture_call_is_made():
    draw = Drawer()
    with pytest.raises(IllustrationError, match="switched off"):
        illustrate("A VPN session lasts 12 hours.", draw=draw, enabled=False)
    assert draw.prompts == []


def test_the_default_is_the_off_setting():
    draw = Drawer()
    with pytest.raises(IllustrationError):
        illustrate("A VPN session lasts 12 hours.", draw=draw)
    assert draw.prompts == []


def test_a_picture_is_made_labelled_and_costed(tmp_path):
    draw = Drawer()
    made = illustrate("A VPN session stays connected for 12 hours [1]. After that sign in again [1].", draw=draw, enabled=True)
    assert made["label"] == LABEL == "AI-generated illustration" and made["cost_usd"] == IMAGE_COST_USD and made["image"] == draw.picture
    assert made["summary"] == "A VPN session stays connected for hours."


def test_only_one_summary_sentence_and_the_fixed_style_are_sent():
    draw = Drawer()
    illustrate("A VPN session stays connected for 12 hours [1]. After that sign in again with your MFA code [1]. Contact bob@northwind.example.", draw=draw, enabled=True)
    assert draw.prompts == [f"A VPN session stays connected for hours. {ILLUSTRATION_STYLE}"]
    style = ILLUSTRATION_STYLE.lower()
    assert all(rule in style for rule in ("no text", "no letters", "no numbers", "no logos", "no people"))


@pytest.mark.parametrize("answer,expected", [
    ("Contact bob@northwind.example or https://intranet.example/x for help with the printer queue.", "Contact or for help with the printer queue."),
    ("Error VPN-809 means the certificate expired and must be renewed.", "Error means the certificate expired and must be renewed."),
    ("To set up MFA, follow these steps:\n1. Install the app.\n2. Scan the code.\nThen you are done with the setup.", "Then you are done with the setup."),
    ("A session lasts 12 hours . After that sign in.", "A session lasts hours."),
    ("**Printing** is limited to 150 colour pages a month.", "Printing is limited to colour pages a month."),
])
def test_the_summary_drops_citations_addresses_codes_and_list_steps(answer, expected):
    assert summary_of(answer) == expected


def test_the_summary_is_capped():
    assert len(summary_of("The printer " + "keeps jamming and " * 40 + "needs a service.")) <= ILLUSTRATION_SUMMARY_CHARS


@pytest.mark.parametrize("answer", ["", "Ok", "Error VPN-809.", "1. Do this.\n2. Do that."])
def test_an_answer_with_nothing_to_draw_makes_no_call(answer):
    draw = Drawer()
    with pytest.raises(IllustrationError, match="not enough"):
        illustrate(answer, draw=draw, enabled=True)
    assert draw.prompts == []


def test_something_that_is_not_a_picture_is_not_shown():
    with pytest.raises(IllustrationError, match="usable picture"):
        illustrate("A VPN session lasts 12 hours.", draw=Drawer(picture=b"<html>not a picture</html>"), enabled=True)


def test_an_unreachable_picture_model_raises_the_usual_error():
    with pytest.raises(LLMError):
        illustrate("A VPN session lasts 12 hours.", draw=Drawer(fail=True), enabled=True)


def test_a_picture_is_logged_by_number_only(tmp_path, monkeypatch):
    import app.calllog as calllog
    logged = []
    monkeypatch.setattr("app.illustrate.log_call", lambda entry: logged.append(entry))
    illustrate("A VPN session lasts 12 hours.", draw=Drawer(), enabled=True)
    assert logged == [{"kind": "illustration", "image_calls": 1, "cost_usd": IMAGE_COST_USD, "prompt_chars": len(prompt_for("A VPN session lasts 12 hours."))}]
