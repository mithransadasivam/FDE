"""Tells you when Activity 1 is done: all five tests pass. No model is used."""

import base64

import pytest

from app.vision import image_part

PNG = b"\x89PNG\r\n\x1a\nfake image bytes"


def test_returns_an_image_url_part():
    part = image_part(PNG, "image/png")
    assert part["type"] == "image_url" and set(part["image_url"]) == {"url"}


def test_the_url_is_a_base64_data_url_with_the_mime_type():
    url = image_part(PNG, "image/png")["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")


def test_the_bytes_survive_the_round_trip():
    url = image_part(PNG, "image/jpeg")["image_url"]["url"]
    assert base64.b64decode(url.split(",", 1)[1]) == PNG


def test_an_unsupported_type_is_refused():
    with pytest.raises(ValueError):
        image_part(PNG, "application/pdf")


def test_an_empty_image_is_refused():
    with pytest.raises(ValueError):
        image_part(b"", "image/png")
