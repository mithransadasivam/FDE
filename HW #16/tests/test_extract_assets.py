"""Task 1 tests for app/extract_assets.py. The model is a fake."""

from datetime import date

from app.extract_assets import extract_asset, parse_asset
from tests.day10_fakes import FakeChatClient

PNG = b"\x89PNG fake"
GOOD = (
    '{"asset_tag": "IT-006078", "device_type": "docking station", "model": "Kestrel Dock 2",'
    ' "serial_number": "DK2-55810-A", "purchase_date": "2024-11-02", "department": "Service Desk"}'
)
BAD_TAG = GOOD.replace("IT-006078", "IT-78")


def test_a_valid_reply_becomes_an_asset_in_one_call():
    fake = FakeChatClient(GOOD)
    asset = extract_asset(PNG, "image/png", client=fake)
    assert asset.asset_tag == "IT-006078" and asset.device_type == "docking station"
    assert len(fake.calls) == 1


def test_the_purchase_date_is_a_real_date():
    assert parse_asset(GOOD).purchase_date == date(2024, 11, 2)


def test_a_reply_inside_json_fences_is_read():
    asset = extract_asset(PNG, "image/png", client=FakeChatClient("```json\n" + GOOD + "\n```"))
    assert asset.serial_number == "DK2-55810-A"


def test_a_bad_tag_gets_one_retry_that_includes_the_error():
    fake = FakeChatClient(BAD_TAG, GOOD)
    asset = extract_asset(PNG, "image/png", client=fake)
    assert asset is not None and len(fake.calls) == 2
    retry = fake.calls[1]["messages"]
    assert retry[-2] == {"role": "assistant", "content": BAD_TAG}
    assert "not valid" in retry[-1]["content"]


def test_two_bad_replies_give_none_after_exactly_two_calls():
    fake = FakeChatClient(BAD_TAG, "still not JSON")
    assert extract_asset(PNG, "image/png", client=fake) is None
    assert len(fake.calls) == 2
