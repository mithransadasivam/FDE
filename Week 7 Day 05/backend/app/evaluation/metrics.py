"""The two measurements every evaluation needs.

Ticket ENG-401: agreement() — do two raters agree (you and Tom, or a judge and Tom)? Cohen's kappa.
Ticket ENG-402: score_run() — how many fields did a run get right, per field and per slice of the data?
"""

import re

from pydantic import BaseModel

FIELDS = ["full_name", "address", "statement_date", "issuer"]


def norm(text: str) -> str:
    """Lower case, letters and digits only: the same comparison the prototype uses."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


class Agreement(BaseModel):
    n: int  # items both raters labelled
    agree: int
    percent: float  # 0–100, 1 decimal
    kappa: float  # Cohen's kappa, 2 decimals
    tp: int  # both say positive
    fp: int  # the rater says positive, the expert says negative
    fn: int  # the rater says negative, the expert says positive
    tn: int  # both say negative
    caught: float | None  # tp / (tp + fn), 2 decimals; None when the expert has no positives
    cleared: float | None  # tn / (tn + fp), 2 decimals; None when the expert has no negatives
    disagreements: list[str]  # the item ids where they differ, sorted


def agreement(rater: dict[str, str], expert: dict[str, str], positive: str) -> Agreement:
    """Compare a rater's labels with the expert's, on the items both labelled.

    Labels are strings; `positive` names the label that means "a problem" (for example "wrong" or "fail").
    Any other label counts as negative.

    - n: the number of item ids in both dicts. agree: how many have the same positive/negative label.
    - percent = round(100 * agree / n, 1).
    - Cohen's kappa = (po - pe) / (1 - pe), where po = agree / n and
      pe = (rater positive share × expert positive share) + (rater negative share × expert negative share).
      If pe == 1 (both raters gave one label to everything), kappa is 1.0 when po == 1, else 0.0.
      Round kappa to 2 decimals.
    - tp, fp, fn, tn as on the class: "positive" is the rater's or expert's problem label.
    - caught = tp / (tp + fn) and cleared = tn / (tn + fp), each rounded to 2 decimals, or None if the divisor is 0.
    - disagreements: the item ids where they differ, sorted.
    - If n is 0, return everything as 0, kappa 0.0, caught and cleared None, no disagreements.
    """
    ids = sorted(set(rater) & set(expert))
    n = len(ids)
    if n == 0:
        return Agreement(n=0, agree=0, percent=0.0, kappa=0.0, tp=0, fp=0, fn=0, tn=0, caught=None, cleared=None, disagreements=[])
    tp = fp = fn = tn = 0
    disagreements = []
    for i in ids:
        r, e = rater[i] == positive, expert[i] == positive
        if r and e:
            tp += 1
        elif r:
            fp += 1
        elif e:
            fn += 1
        else:
            tn += 1
        if r != e:
            disagreements.append(i)
    agree = tp + tn
    po = agree / n
    pr, pe_pos = (tp + fp) / n, (tp + fn) / n
    pe = pr * pe_pos + (1 - pr) * (1 - pe_pos)
    kappa = (1.0 if po == 1 else 0.0) if pe == 1 else (po - pe) / (1 - pe)
    return Agreement(
        n=n, agree=agree, percent=round(100 * agree / n, 1), kappa=round(kappa, 2),
        tp=tp, fp=fp, fn=fn, tn=tn,
        caught=round(tp / (tp + fn), 2) if tp + fn else None,
        cleared=round(tn / (tn + fp), 2) if tn + fp else None,
        disagreements=disagreements,
    )


class Score(BaseModel):
    correct: int
    total: int
    accuracy: float  # 0–100, 1 decimal


class FieldError(BaseModel):
    case_id: str
    field: str
    got: str
    expected: str


class RunScore(BaseModel):
    overall: Score
    per_field: dict[str, Score]
    per_slice: dict[str, Score]
    errors: list[FieldError]


def _score(correct: int, total: int) -> Score:
    return Score(correct=correct, total=total, accuracy=round(100 * correct / total, 1) if total else 0.0)


def score_run(outputs: dict[str, dict[str, str]], labels: dict[str, dict[str, str]], slices: dict[str, list[str]]) -> RunScore:
    """Score a run's field values against the expert's labels.

    outputs: {case_id: {field: value}} from the run. labels: {case_id: {field: right value, ...}} from the expert.
    slices: {case_id: [slice, ...]} such as "two_dates" or "clean".

    - Score only cases that are in both outputs and labels, and only the four FIELDS. A missing field counts as "".
    - A field is right when norm(value) == norm(label).
    - overall: every scored field. per_field: one Score per name in FIELDS, in that order.
    - per_slice: one Score per slice, over all four fields of the cases in that slice; keys sorted alphabetically.
    - errors: one FieldError per wrong field, sorted by case_id, then by the order of FIELDS.
    - accuracy = round(100 * correct / total, 1), or 0.0 when total is 0.
    """
    ids = sorted(set(outputs) & set(labels))
    correct = {f: 0 for f in FIELDS}
    by_slice: dict[str, list[int]] = {}
    errors: list[FieldError] = []
    for cid in ids:
        right = 0
        for f in FIELDS:
            got, expected = outputs[cid].get(f) or "", labels[cid].get(f) or ""
            if norm(got) == norm(expected):
                correct[f] += 1
                right += 1
            else:
                errors.append(FieldError(case_id=cid, field=f, got=got, expected=expected))
        for sl in slices.get(cid, []):
            t = by_slice.setdefault(sl, [0, 0])
            t[0] += right
            t[1] += len(FIELDS)
    return RunScore(
        overall=_score(sum(correct.values()), len(ids) * len(FIELDS)),
        per_field={f: _score(correct[f], len(ids)) for f in FIELDS},
        per_slice={k: _score(*by_slice[k]) for k in sorted(by_slice)},
        errors=errors,
    )

