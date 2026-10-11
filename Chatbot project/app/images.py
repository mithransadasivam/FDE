"""Images a user attaches: check them, make them smaller, and turn them into what a vision model accepts.

Everything here is plain code with no model and no network. A bad file is refused BEFORE anything is sent anywhere.
Nothing is written to disk: an image lives in memory for the length of one request (and, as a small preview, for the open page).
"""
import base64
import io

from PIL import Image, ImageOps

from app.config import IMAGE_MAX_BYTES, IMAGE_MAX_SIDE, IMAGE_THUMBNAIL_SIDE, IMAGE_TYPES

MAX_PIXELS = 40_000_000  # a small file can still unpack to a huge picture; refuse those too

MSG_NOT_A_PICTURE = "That file is not a PNG, JPEG or WebP picture. Please attach a screenshot in one of those formats."
MSG_TOO_BIG = f"That picture is bigger than {IMAGE_MAX_BYTES // (1024 * 1024)} MB. Please attach a smaller one."
MSG_UNREADABLE = "That picture could not be opened. It may be damaged. Please try another."
MSG_EMPTY_FILE = "That file is empty."


class ImageError(ValueError):
    """The attached file cannot be used. The message is friendly and safe to show."""


def sniff_type(data: bytes) -> str | None:
    """The picture type from the file's first bytes, never from its name: a program renamed to .png is not a PNG."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def check_image(data: bytes) -> str:
    """Return the picture's type if it can be used. Raises ImageError (with a friendly message) otherwise."""
    if not data:
        raise ImageError(MSG_EMPTY_FILE)
    if len(data) > IMAGE_MAX_BYTES:
        raise ImageError(MSG_TOO_BIG)
    mime = sniff_type(data)
    if mime not in IMAGE_TYPES:
        raise ImageError(MSG_NOT_A_PICTURE)
    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            if width * height > MAX_PIXELS:
                raise ImageError(MSG_TOO_BIG)
            image.verify()
    except ImageError:
        raise
    except Exception as err:  # noqa: BLE001: Pillow raises several kinds of error for damaged pictures
        raise ImageError(MSG_UNREADABLE) from err
    return mime


def _flatten(image: Image.Image) -> Image.Image:
    """RGB, with transparent areas turned white, and the camera's rotation applied. Re-encoding also drops all metadata (location, device)."""
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.split()[3])
        return background
    return image.convert("RGB")


def resize_for_model(data: bytes, max_side: int = IMAGE_MAX_SIDE) -> tuple[bytes, str, tuple[int, int]]:
    """Make the picture no bigger than `max_side` pixels on its longest side (never larger than it was), without its metadata.

    Returns (bytes, mime type, (width, height)). Screenshots stay PNG so small text stays sharp; photos stay JPEG.
    """
    mime = check_image(data)
    with Image.open(io.BytesIO(data)) as source:
        image = _flatten(source)
    longest = max(image.size)
    if longest > max_side:
        scale = max_side / longest
        image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.LANCZOS)
    out = io.BytesIO()
    if mime == "image/jpeg":
        image.save(out, "JPEG", quality=88, optimize=True)
        return out.getvalue(), "image/jpeg", image.size
    image.save(out, "PNG", optimize=True)
    return out.getvalue(), "image/png", image.size


def thumbnail(data: bytes, side: int = IMAGE_THUMBNAIL_SIDE) -> bytes:
    """A small PNG preview, for showing the picture in the chat. Never larger than the original."""
    with Image.open(io.BytesIO(data)) as source:
        image = _flatten(source)
    image.thumbnail((side, side))
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def data_uri(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def image_part(data: bytes, mime: str) -> dict:
    """The piece of a chat message that carries a picture, in the form the model API expects."""
    return {"type": "image_url", "image_url": {"url": data_uri(data, mime)}}
