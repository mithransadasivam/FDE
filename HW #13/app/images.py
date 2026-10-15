"""Day 10: make images smaller before sending them, to save tokens and time.

Homework, Task 2: fill in resize_for_model(). Check it with tests/test_images.py.
"""

import io  # noqa: F401  (you will need it)
from pathlib import Path  # noqa: F401  (you will need it)

from PIL import Image  # noqa: F401  (you will need it)


def resize_for_model(path, max_side: int | None) -> tuple[bytes, tuple[int, int]]:
    """TODO (homework, Task 2): shrink an image so its longest side is at most max_side pixels.

    Returns (PNG bytes, (width, height) of the image that was returned).
    Rules (tests/test_images.py checks each one):
    - open the image with Image.open(path)
    - if max_side is None, or the longest side is already max_side or less, keep the size
      (never make an image bigger)
    - otherwise scale BOTH sides by the same factor, max_side / longest side, rounding each
      to the nearest whole pixel, with Image.LANCZOS
    - save the result as PNG into an io.BytesIO and return its bytes and the new size
    """
    image = Image.open(Path(path))
    width, height = image.size
    longest = max(width, height)
    if max_side is not None and longest > max_side:
        scale = max_side / longest
        image = image.resize(
            (round(width * scale), round(height * scale)), Image.LANCZOS
        )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue(), image.size
