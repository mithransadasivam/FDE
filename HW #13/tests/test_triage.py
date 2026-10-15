"""Tells you when Activity 2 is done: all five tests pass. The model is a fake."""

from app.triage import triage_screenshot
from tests.day10_fakes import FakeChatClient

PNG = b"\x89PNG fake"
GOOD = (
    '{"error_code": "VPN-809", "application": "SecureLink VPN", "summary": "The VPN certificate has expired.",'
    ' "severity": "P3", "next_step": "Renew the certificate from the self-service portal."}'
)
BAD = '{"error_code": "VPN-809", "application": "SecureLink VPN", "severity": "urgent"}'


def test_a_valid_reply_becomes_a_ticket_in_one_call():
    fake = FakeChatClient(GOOD)
    ticket = triage_screenshot(PNG, "image/png", client=fake)
    assert ticket.error_code == "VPN-809" and ticket.severity == "P3"
    assert len(fake.calls) == 1


def test_the_image_is_sent_at_temperature_zero_with_the_given_model():
    fake = FakeChatClient(GOOD)
    triage_screenshot(PNG, "image/png", client=fake, model="vision-model")
    call = fake.calls[0]
    assert call["temperature"] == 0 and call["model"] == "vision-model"
    parts = call["messages"][0]["content"]
    assert any(
        p["type"] == "image_url"
        and p["image_url"]["url"].startswith("data:image/png;base64,")
        for p in parts
    )


def test_a_reply_inside_json_fences_is_read():
    ticket = triage_screenshot(
        PNG, "image/png", client=FakeChatClient("```json\n" + GOOD + "\n```")
    )
    assert ticket.application == "SecureLink VPN"


def test_a_bad_reply_gets_one_retry_that_includes_the_error():
    fake = FakeChatClient(BAD, GOOD)
    ticket = triage_screenshot(PNG, "image/png", client=fake)
    assert ticket is not None and len(fake.calls) == 2
    retry = fake.calls[1]["messages"]
    assert retry[-2] == {"role": "assistant", "content": BAD}
    assert retry[-1]["role"] == "user" and "not valid" in retry[-1]["content"]


def test_two_bad_replies_give_none_after_exactly_two_calls():
    fake = FakeChatClient(BAD, "still not JSON")
    assert triage_screenshot(PNG, "image/png", client=fake) is None
    assert len(fake.calls) == 2
