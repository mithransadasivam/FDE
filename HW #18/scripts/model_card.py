"""Day 18: check the model card and write it as a page.

python -m scripts.model_card          (reads governance/model_card.json, writes governance/MODEL_CARD.md)

Lists every gap (a missing section, a result without evidence, too few limitations). The page is
written either way, with the gaps at the end, so reviewers see what is still missing.
Exit code 0 when the card is complete, 1 when it has gaps.
"""

import json
import sys
from pathlib import Path

from app.model_card import card_gaps, render_markdown

CARD = "governance/model_card.json"
PAGE = "governance/MODEL_CARD.md"


def main():
    card = json.loads(Path(CARD).read_text(encoding="utf-8"))
    gaps = card_gaps(card)
    Path(PAGE).write_text(render_markdown(card, gaps), encoding="utf-8")
    for g in gaps:
        print(f"  GAP  {g}")
    print(f"\n{'COMPLETE' if not gaps else f'{len(gaps)} gap(s)'}: wrote {PAGE}")
    sys.exit(1 if gaps else 0)


if __name__ == "__main__":
    main()
