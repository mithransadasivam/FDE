"""Day 10, Activity 1: send one screenshot to the vision model and print its description.

python -m scripts.describe_image
python -m scripts.describe_image data/screenshots/Day10_Slide09_screenshot_03_printer.png
"""

import argparse

from PIL import Image

from app.vision import ask_about_image, estimate_image_tokens

DEFAULT = "data/screenshots/Day10_Slide09_screenshot_01_vpn.png"
PROMPT = "Describe this screenshot for an IT service desk: which application is it, what went wrong, and what should the user do next?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", nargs="?", default=DEFAULT)
    ap.add_argument("--prompt", default=PROMPT)
    args = ap.parse_args()
    width, height = Image.open(args.image).size
    print(
        f"Image: {args.image}  ({width} x {height} pixels, about {estimate_image_tokens(width, height)} input tokens)\n"
    )
    print(ask_about_image(args.image, args.prompt))


if __name__ == "__main__":
    main()
