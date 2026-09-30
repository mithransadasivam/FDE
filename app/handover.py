"""Handover note with injection defences (Day 4 homework, Task 4).

summarise() sends a support thread through prompts/handover_note_v5.txt (untrusted text in
<thread> tags, stated to be data) and then checks the reply in plain Python. The wording
lowers the odds of a hijack; validate_note() is what holds.

Run from the repository root:
    python -m app.handover data/Day04_HW_Slide06_thread_poisoned.txt
    python -m app.handover data/Day04_HW_Slide06_thread_poisoned.txt --undefended
"""

import argparse
import re
from pathlib import Path

from app.clients import HOSTED_MODEL, hosted_client

ROOT = Path(__file__).resolve().parent.parent
DEFENDED_PROMPT = "prompts/handover_note_v5.txt"
UNDEFENDED_PROMPT = "prompts/handover_note_v4.txt"  # before the injection defences
MAX_BULLET_CHARS = 300

# A note may only claim the ticket is finished if the customer confirmed a fix.
RESOLUTION_CLAIM = re.compile(
    r"\b(resolved|no action|no further action|close the ticket|closed)\b", re.IGNORECASE
)
# Deliberately narrower than RESOLUTION_CLAIM: "resolved" is what an attacker writes.
CONFIRMATION = re.compile(r"confirm|works now|working now|fixed now|that fixed", re.IGNORECASE)


class InvalidNote(ValueError):
    """The model's reply broke the output contract, so it is not used."""


def neutralise(thread):
    """Stop the thread closing our <thread> tag early and escaping the data block."""
    return re.sub(r"</?\s*thread\s*>", "[thread tag removed]", thread, flags=re.IGNORECASE)


def customer_confirmed(thread):
    """True if a customer line in the thread confirms the problem is fixed."""
    return any(
        line.lstrip().lower().startswith("customer") and CONFIRMATION.search(line)
        for line in thread.splitlines()
    )


def validate_note(note, thread):
    """Return the note if it is exactly three short bullets, else raise InvalidNote."""
    lines = [line.strip() for line in (note or "").strip().splitlines() if line.strip()]
    if len(lines) != 3 or not all(line.startswith("- ") for line in lines):
        raise InvalidNote("expected exactly three bullets that start with '- '")
    if any(len(line) > MAX_BULLET_CHARS for line in lines):
        raise InvalidNote(f"a bullet is longer than {MAX_BULLET_CHARS} characters")
    claim = RESOLUTION_CLAIM.search(note)
    if claim and not customer_confirmed(thread):
        raise InvalidNote(f"claims '{claim.group(0)}' but the customer never confirmed a fix")
    return "\n".join(lines)


def summarise(thread, client, model=HOSTED_MODEL, defended=True):
    """Return the handover note for a thread. defended=False skips the Task 4 defences."""
    path = ROOT / (DEFENDED_PROMPT if defended else UNDEFENDED_PROMPT)
    template = path.read_text(encoding="utf-8")
    data = neutralise(thread) if defended else thread
    r = client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=300,
        messages=[{"role": "user", "content": template.replace("{text}", data)}],
    )
    note = r.choices[0].message.content or ""
    return validate_note(note, thread) if defended else note.strip()


def main():
    ap = argparse.ArgumentParser(description="Turn a support thread into a handover note")
    ap.add_argument("thread", help="path to a text file holding the thread")
    ap.add_argument("--undefended", action="store_true", help="v4 prompt, no validation")
    args = ap.parse_args()
    thread = Path(args.thread).read_text(encoding="utf-8")
    try:
        print(summarise(thread, hosted_client(), defended=not args.undefended))
    except InvalidNote as e:
        print(f"REJECTED: {e}")


if __name__ == "__main__":
    main()
