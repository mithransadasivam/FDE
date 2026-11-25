"""The small model: train it on the teacher's labels, keep it as a file, and use it (done: you do not change this file).

It is a logistic regression (scikit-learn): for each word, one weight per (feature, label). A word's score for a
label is the sum of the weights of its features; softmax turns the five scores into five probabilities that add up
to 1. Training finds the weights that make the teacher's labels most likely. On a laptop it takes a few seconds.

The trained model is a table of weights, kept as JSON in engagement/distil/models/<name>.json (a few hundred KB):
you can open it and read what it learned. Using it needs no scikit-learn and no network: a sum and a softmax.
"""

import json
import os
import threading
import time
from datetime import datetime, timezone

import numpy as np

from app import store
from app.distil.features import page_features
from app.distil.labels import word_labels
from app.distil.reads import words_of

LABELS = ["O", "full_name", "address", "statement_date", "issuer"]


def training_rows(reads: list[dict]) -> dict:
    """Features and labels for every word of every read that word_labels() keeps (ENG-1101)."""
    X, y, kept, skipped = [], [], [], []
    for r in reads:
        labels = word_labels(r)
        if labels is None:
            skipped.append(r["doc_id"])
            continue
        X += page_features(words_of(r), r["kind"])
        y += labels
        kept.append(r["doc_id"])
    return {"X": X, "y": y, "kept": kept, "skipped": skipped}


class SmallModel:
    def __init__(self, meta: dict, features: dict[str, int], coef: np.ndarray, intercept: np.ndarray):
        self.meta, self.features, self.coef, self.intercept = meta, features, coef, intercept
        self.classes = meta["classes"]

    def probs(self, words, kind: str) -> np.ndarray:
        """One row per word, one column per label (self.classes): the probability of each label."""
        rows = page_features(words, kind)
        scores = np.tile(self.intercept, (len(rows), 1))
        for i, feats in enumerate(rows):
            idx = [self.features[k] for k in feats if k in self.features]
            if idx:
                scores[i] += self.coef[:, idx].sum(axis=1)
        scores -= scores.max(axis=1, keepdims=True)
        e = np.exp(scores)
        return e / e.sum(axis=1, keepdims=True)

    def weights_for(self, label: str, top: int = 12) -> list[dict]:
        """The features that count most towards a label: what the model learned, in words."""
        j = self.classes.index(label)
        names = {v: k for k, v in self.features.items()}
        order = np.argsort(-self.coef[j])[:top]
        return [{"feature": names[i], "weight": round(float(self.coef[j][i]), 2)} for i in order]


def train(name: str, reads: list[dict], read_files: list[str], c: float = 1.0) -> SmallModel:
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.linear_model import LogisticRegression

    started = time.perf_counter()
    rows = training_rows(reads)
    if not rows["y"]:
        raise ValueError("No reads to train on: word_labels() left every read out")
    vec = DictVectorizer()
    X = vec.fit_transform(rows["X"])
    clf = LogisticRegression(max_iter=300, C=c)
    clf.fit(X, rows["y"])
    seconds = round(time.perf_counter() - started, 1)
    classes = [str(k) for k in clf.classes_]
    meta = {"name": name, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "read_files": read_files,
            "reads": len(reads), "kept": len(rows["kept"]), "skipped": len(rows["skipped"]), "words": len(rows["y"]),
            "features": X.shape[1], "classes": classes, "train_seconds": seconds,
            "kinds": sorted({r["kind"] for r in reads if r["doc_id"] in set(rows["kept"])})}
    model = SmallModel(meta, {k: int(v) for k, v in vec.vocabulary_.items()}, np.asarray(clf.coef_), np.asarray(clf.intercept_))
    save(model)
    return model


def save(model: SmallModel) -> None:
    """Readable where it matters (meta), compact where it is big (one line per label of weights)."""
    p = store.path(f"distil/models/{model.meta['name']}.json")
    rows = ",\n  ".join(json.dumps([round(float(v), 4) for v in row]) for row in model.coef)
    text = ("{\n" f' "meta": {json.dumps(model.meta, indent=2)},\n'
            f' "features": {json.dumps(model.features, separators=(",", ":"))},\n'
            f' "intercept": {json.dumps([round(float(v), 4) for v in model.intercept])},\n'
            f' "coef": [\n  {rows}\n ]\n' "}\n")
    tmp = p.with_name(f"{p.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(p)


def load(name: str) -> SmallModel | None:
    d = store.load(f"distil/models/{name}.json", None)
    if d is None:
        return None
    return SmallModel(d["meta"], d["features"], np.asarray(d["coef"]), np.asarray(d["intercept"]))
