"""Tells you when homework Task 2 is done: all five tests pass. No model is used."""

import io

from PIL import Image

from app.images import resize_for_model


def make(tmp_path, size, name="img.png"):
    path = tmp_path / name
    Image.new("RGB", size, "white").save(path)
    return path


def test_a_wide_image_is_scaled_to_the_maximum_side(tmp_path):
    _, size = resize_for_model(make(tmp_path, (2000, 1000)), 1000)
    assert size == (1000, 500)


def test_a_tall_image_keeps_its_shape(tmp_path):
    _, size = resize_for_model(make(tmp_path, (600, 1200)), 300)
    assert size == (150, 300)


def test_a_small_image_is_never_made_bigger(tmp_path):
    _, size = resize_for_model(make(tmp_path, (400, 300)), 1000)
    assert size == (400, 300)


def test_no_maximum_keeps_the_original_size(tmp_path):
    _, size = resize_for_model(make(tmp_path, (1001, 333)), None)
    assert size == (1001, 333)


def test_the_bytes_are_a_png_of_the_new_size(tmp_path):
    data, size = resize_for_model(make(tmp_path, (1000, 620), "shot.jpg"), 500)
    image = Image.open(io.BytesIO(data))
    assert image.format == "PNG" and image.size == size == (500, 310)
