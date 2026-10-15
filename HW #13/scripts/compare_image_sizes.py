"""Day 10 homework, Task 2: triage the same screenshots at several image sizes and compare
accuracy, estimated input tokens and time.

    python -m scripts.compare_image_sizes
    python -m scripts.compare_image_sizes --sizes 0 1024 512 256     (0 means the original size)
"""

import argparse

from scripts.triage_screenshots import EXPECTED, FIELDS, FOLDER, run_triage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="+", default=[0, 768, 384])
    ap.add_argument("--folder", default=FOLDER)
    ap.add_argument("--expected", default=EXPECTED)
    args = ap.parse_args()
    print(
        f"{'longest side':>13} "
        + "".join(f"{f:>13}" for f in FIELDS)
        + f"{'tokens':>9}{'seconds':>9}"
    )
    for size in args.sizes:
        _, s = run_triage(args.folder, args.expected, size or None, quiet=True)
        label = "original" if not size else f"{size} px"
        print(
            f"{label:>13} "
            + "".join(f"{s.get(f, '-'):>13}" for f in FIELDS)
            + f"{s['avg_tokens']:>9}{s['avg_seconds']:>9}"
        )
    print("\ntokens: estimated input tokens per image (width x height / 750)")


if __name__ == "__main__":
    main()
