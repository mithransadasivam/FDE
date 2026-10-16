"""Name similarity (policy §3.3): normalise, then take the better of two measures.

1. normalise: lower case, "&" becomes "and", punctuation removed, legal suffixes (ltd, limited, plc, gmbh, ...) removed
2. character similarity (difflib ratio) catches spelling variations ("Veltrax" vs "Veltrix")
3. word-order-free similarity catches reordered names ("Supply Marine Veltrax")
Score is 0.0 to 1.0. The thresholds that mean "duplicate" or "a person must look" are in rules.py.
"""
import re
from difflib import SequenceMatcher

LEGAL_SUFFIXES = {"ltd", "limited", "plc", "llc", "llp", "inc", "incorporated", "gmbh", "co", "company", "sa", "sl",
                  "ab", "bv", "ag", "corp", "corporation", "the"}


def normalize(name: str) -> str:
    text = name.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    words = [w for w in text.split() if w not in LEGAL_SUFFIXES]
    return " ".join(words)


def similarity(a: str, b: str) -> float:
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    plain = SequenceMatcher(None, na, nb).ratio()
    sorted_ = SequenceMatcher(None, " ".join(sorted(na.split())), " ".join(sorted(nb.split()))).ratio()
    return round(max(plain, sorted_), 3)
