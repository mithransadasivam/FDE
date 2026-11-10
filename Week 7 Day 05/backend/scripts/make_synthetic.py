"""Generate synthetic edge cases for one slice with the model, into evals/synthetic/. Run from backend/:

    python -m scripts.make_synthetic two_dates --n 20

Slices: two_dates, joint_names, issuer_variant, address_order. Synthetic cases are text only (OCR words and labels):
read a few before you trust them, and keep them separate from the real cases when you report a score.
"""

import argparse
import json

from app.config import SYNTHETIC_DIR
from app.evaluation.service import SLICES, make_synthetic
from app.llm import llm_client


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slice", choices=list(SLICES))
    ap.add_argument("--n", type=int, default=20)
    a = ap.parse_args()
    made = make_synthetic(a.slice, a.n, llm_client())
    print(f"Wrote {len(made)} synthetic cases for {a.slice} to evals/synthetic/: {', '.join(made)}")
    if made:
        d = json.loads((SYNTHETIC_DIR / f"{made[0]}.json").read_text(encoding="utf-8"))
        print(f"\nFirst one, {made[0]}:\n  " + " ".join(w["text"] for w in d["words"]))
        print(f"  labels: {d['labels']}")


if __name__ == "__main__":
    main()
