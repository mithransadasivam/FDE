"""Homework Task 1: which kinds of document should the small model be retrained for?

A kind the small model has not learned (a council tax bill) is not a disaster: the cascade sends it to the pilot.
It is a cost: every one of them takes two Sonnet calls and waits for them. The team watches, for each kind of document,
what share goes to the teacher, and retrains when a kind keeps going there.
"""


def retrain_candidates(rows: list[dict], max_teacher_share: float = 0.5, min_docs: int = 10) -> list[dict]:
    """rows: one per document, {"doc_id", "kind", "route": "small" | "teacher", "reasons": [...]}.
    Return one entry per kind, sorted by kind name: {"kind", "documents", "to_teacher", "share" (to_teacher / documents,
    rounded to 3 decimals), "top_reason" (the field named most often in the reasons of that kind's teacher documents,
    or None; a reason starts with the field name), "retrain": share > max_teacher_share and documents >= min_docs}.
    Spot checks are not a reason to retrain: a row whose reasons are exactly ["spot check"] counts as "small".
    """
    by_kind: dict[str, list[dict]] = {}
    for r in rows:
        by_kind.setdefault(r["kind"], []).append(r)
    out = []
    for kind in sorted(by_kind):
        docs = by_kind[kind]
        teacher = [r for r in docs if r["route"] == "teacher" and r["reasons"] != ["spot check"]]
        named: dict[str, int] = {}
        for r in teacher:
            for reason in r["reasons"]:
                field = reason.split(" ")[0]
                named[field] = named.get(field, 0) + 1
        share = round(len(teacher) / len(docs), 3)
        top = max(named, key=named.get) if named else None
        out.append({"kind": kind, "documents": len(docs), "to_teacher": len(teacher), "share": share,
                    "top_reason": top, "retrain": share > max_teacher_share and len(docs) >= min_docs})
    return out
