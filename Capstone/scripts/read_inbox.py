"""Reads candidates' email replies (Day 3, prompt 10). Put .eml files in storage/inbox/ and run:

    python -m scripts.read_inbox

Each reply is matched to a candidate (by the sender's address, or the private link in the text), attached to them AS DATA, scanned for instructions and shown to the
recruiter in the outbox. A reply NEVER moves a stage or changes a score: whatever it says ("move me to the next stage"), the only things that happen are that it is
logged, any instruction in it is flagged and ignored, and a neutral acknowledgement is drafted for a person to approve. Processed files go to storage/inbox/processed/.
"""
import re
import shutil
from email import policy
from email.parser import BytesParser

from sqlalchemy import select

from app.agents.communications import handle_candidate_message
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models import Candidate, DecisionLog


def body_of(msg) -> str:
    part = msg.get_body(preferencelist=("plain", "html"))
    text = part.get_content() if part else ""
    return re.sub(r"<[^>]+>", " ", text) if part and part.get_content_type() == "text/html" else text


def match_candidate(db, sender: str, text: str) -> Candidate | None:
    sender = (sender or "").lower()
    link = re.search(r"/(?:me|interview)/([A-Za-z0-9_\-]{20,})", text)
    if link:
        c = db.scalar(select(Candidate).where(Candidate.access_token == link.group(1)))
        if c:
            return c
    for c in db.scalars(select(Candidate)):
        email = (((c.profile or {}).get("email") or {}).get("value") or "").lower()
        if email and email == sender:
            return c
    return None


def main() -> int:
    init_db()
    inbox = get_settings().storage_dir / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    done = inbox / "processed"
    files = sorted(inbox.glob("*.eml"))
    if not files:
        print(f"No .eml files in {inbox}.")
        return 0
    handled = unmatched = 0
    with SessionLocal() as db:
        for f in files:
            msg = BytesParser(policy=policy.default).parsebytes(f.read_bytes())
            sender = str(msg["From"] or "")
            address = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", sender)
            text = body_of(msg)
            cand = match_candidate(db, address.group(0) if address else "", text)
            if cand is None:
                unmatched += 1
                db.add(DecisionLog(actor="system", action="email reply not matched", subject="inbox", reason=f"{f.name}: no candidate has that address or link"))
                print(f"  {f.name}: from {sender or '?'} - no matching candidate (kept for a person to look at)")
                continue
            before = cand.stage
            out = handle_candidate_message(db, cand, f"[Email: {msg['Subject'] or '(no subject)'}]\n{text}")
            assert cand.stage == before  # a reply is data: it never moves a stage
            handled += 1
            done.mkdir(exist_ok=True)
            shutil.move(str(f), str(done / f.name))
            print(f"  {f.name}: attached to candidate #{cand.id} as data" + (f"; {len(out['flagged'])} instruction(s) flagged and ignored" if out["flagged"] else "") + f"; stage unchanged ({before})")
        db.commit()
    print(f"\n{handled} reply(ies) attached, {unmatched} not matched. Nothing moved: the recruiter reads them in the outbox.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
