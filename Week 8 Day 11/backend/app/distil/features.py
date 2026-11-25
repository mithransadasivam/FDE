"""What the small model looks at for one word (done: you do not change this file for a ticket).

The small model labels every word on the page: full_name, address, statement_date, issuer, or O (none of them).
It cannot read like Sonnet. It sees a handful of facts about each word, and learns from the teacher's answers
how much each fact counts towards each label. Those facts are the features:

- the word itself, lower case ("statement", "road"), with numbers folded into <num>
- its shape: "Xxxx" for a capitalised word, "dd" for two digits, "XXd" for a postcode's first half
- what it is: a title (Mr, Mrs), a month, a year, a day number, half a postcode
- the three words before it and the three after it
- where it is on the page (which twentieth down, which fifth across), and the first word of its line
- the kind of document (a bill, a bank statement)

Example: "06" in "Statement date 06 Oct 2026" has w=<num>, shape=dd, daynum, p1=date, p2=statement, n1=oct, n2=<num>.
The teacher has labelled thousands of words like it statement_date, so the model learns that p1=date and
p2=statement count strongly towards statement_date, and that p1=to (the end of a statement period) does not.
"""

import re

MONTHS = {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"}
TITLES = {"mr", "mrs", "ms", "miss", "dr"}


def shape(text: str) -> str:
    s = re.sub(r"[A-Z]", "X", text)
    s = re.sub(r"[a-z]", "x", s)
    s = re.sub(r"\d", "d", s)
    return re.sub(r"(.)\1{2,}", r"\1\1", s)


def token(text: str) -> str:
    low = text.lower().strip(".,:;")
    return "<num>" if re.fullmatch(r"[\d,.\-/£%]+", low) else low


def word_features(words, i: int, kind: str) -> dict:
    """The features of words[i] (an OcrWord) on a document of this kind, as {name: 1}."""
    w = words[i]
    text, low = w.text, w.text.lower().strip(".,:;")
    x0, y0 = w.box[0], w.box[1]
    f = {"bias": 1, "w=" + token(text): 1, "shape=" + shape(text): 1, "kind=" + kind: 1,
         "y=" + str(int(y0 * 20)): 1, "x=" + str(int(x0 * 5)): 1, "idx=" + str(min(i, 40) // 4): 1}
    if low in TITLES:
        f["title"] = 1
    if low in MONTHS:
        f["month"] = 1
    if re.fullmatch(r"20\d\d", low):
        f["year"] = 1
    if re.fullmatch(r"\d{1,2}", low):
        f["daynum"] = 1
    if re.fullmatch(r"[A-Z]{1,2}\d{1,2}", text):
        f["pc_out"] = 1
    if re.fullmatch(r"\d[A-Z]{2}", text):
        f["pc_in"] = 1
    if text[:1].isupper():
        f["cap"] = 1
    for k in (1, 2, 3):
        f[f"p{k}=" + (token(words[i - k].text) if i - k >= 0 else "<s>")] = 1
        f[f"n{k}=" + (token(words[i + k].text) if i + k < len(words) else "</s>")] = 1
    before = [v for v in words if abs(v.box[1] - y0) < 0.006 and v.box[0] < x0]  # earlier words on the same line
    f["lhead=" + (token(min(before, key=lambda v: v.box[0]).text) if before else "<line>")] = 1
    f["lpos=" + str(min(len(before), 4))] = 1
    return f


def page_features(words, kind: str) -> list[dict]:
    return [word_features(words, i, kind) for i in range(len(words))]
