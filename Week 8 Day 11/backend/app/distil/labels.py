"""Ticket ENG-1101: turn the teacher's reads into training labels, and keep only the reads the teacher is sure of.

The small model learns one label per word. The teacher's parser reading cites the words it used for each field,
so every cited word gets that field's name as its label, and every other word gets "O" (none of the four fields).

Example: the parser reading of P-0001 says full_name "Mr Harvey Patel" from w012, w013, w014. Those three words are
labelled full_name. "Statement" (w015) is cited by no field, so it is labelled O.

The teacher is wrong about one statement date in five: it reads the statement period's end. If the small model
learns from those reads, it learns that mistake too. Nobody keyed these documents, so the only check is the
teacher's second reading: the vision reading. Where the two readings disagree, at least one is wrong.
"""

from app.distil.reads import agree, norm  # noqa: F401  (norm: compare values ignoring case, spaces and punctuation)
from app.prototype.models import FIELDS

OTHER = "O"


def word_labels(read: dict) -> list[str] | None:
    """One label per word of the read, in the order of read["words"]: the field whose parser reading cites the word,
    or "O". Return None to leave the whole read out of training when the teacher is not sure of it:
    - for any of the four fields, the parser value and the vision value disagree (use agree(read, field)), or
    - for any of the four fields, the parser reading cites no words.
    """
    for f in FIELDS:
        if not agree(read, f) or not read["parser"][f]["word_ids"]:
            return None
    labels = [OTHER] * len(read["words"])
    where = {w[0]: i for i, w in enumerate(read["words"])}
    for f in FIELDS:
        for wid in read["parser"][f]["word_ids"]:
            labels[where[wid]] = f
    return labels
