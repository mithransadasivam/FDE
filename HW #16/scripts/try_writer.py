"""Day 14: one handoff on its own. The writer receives the class research notes and must hand back a
checked Notice. Shows the notice, and how many model calls it took (2 means the first reply was
rejected and the writer was asked again).

python -m scripts.try_writer
python -m scripts.try_writer --notes data/Day14_Slide09_research_notes.json
"""

import argparse
import json
from pathlib import Path

from app.handoffs import HandoffError, ResearchNotes
from app.meter import Meter
from app.rag import llm_client
from app.team import show, write

NOTES = "data/Day14_Slide09_research_notes.json"

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--notes", default=NOTES)
    a = p.parse_args()
    notes = ResearchNotes(**json.loads(Path(a.notes).read_text(encoding="utf-8")))
    print(f"Research notes: {len(notes.facts)} facts about {notes.topic!r}\n")
    meter = Meter(llm_client())
    try:
        notice = write(notes, meter)
        print("Writer -> Notice (checked):")
        print(show(notice.model_dump()))
    except HandoffError as e:
        print(f"The writer's reply could not be used, even after one retry: {e}")
    print(f"\nModel calls: {meter.summary()['calls']}")
