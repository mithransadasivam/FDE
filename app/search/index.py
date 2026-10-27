"""Hybrid search: BM25 keywords + hashed TF-IDF vectors, fused with reciprocal rank fusion, then reranked (Days 6-7).

Pure Python and numpy, so it runs everywhere with no model. A real embedding model can replace _vectorise() later.
CV chunks come from the BLIND record, so search results never contain identity.
"""
import math
import re
import zlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.agents.base import register_tool
from app.config import get_settings
from app.evidence import blind_text  # noqa: F401  (kept importable for callers)

STOP = {"the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "with", "who", "has", "have", "had", "is", "are", "was", "were", "me", "show",
        "which", "that", "this", "do", "does", "any", "all", "list", "find", "candidates", "candidate", "people", "anyone", "run", "ran", "used", "use"}
SYNONYMS = {"k8s": "kubernetes", "kube": "kubernetes", "cka": "kubernetes", "aws": "cloud", "azure": "cloud", "tf": "terraform",
            "monitoring": "prometheus grafana", "scripting": "python bash powershell", "networking": "network dns"}
DIM = 512


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9+#]+", (text or "").lower())
    out = []
    for w in words:
        if w in STOP or len(w) < 2:
            continue
        out.append(w[:-1] if w.endswith("s") and len(w) > 3 else w)
    return out


def rewrite_query(q: str) -> str:
    """Query rewriting: expand abbreviations and sloppy words into the terms the CVs use."""
    extra = [SYNONYMS[w] for w in re.findall(r"[a-z0-9+#]+", q.lower()) if w in SYNONYMS]
    return q + " " + " ".join(extra) if extra else q


@dataclass
class Chunk:
    id: str
    source: str  # cv, policy or question
    ref: str  # candidate id, policy section number or question id
    section: str
    text: str
    meta: dict = field(default_factory=dict)


@dataclass
class Hit:
    chunk: Chunk
    score: float
    why: str = ""


class HybridIndex:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.docs = [tokenize(c.text + " " + c.section) for c in chunks]
        self.df = Counter(t for d in self.docs for t in set(d))
        self.n = max(1, len(chunks))
        self.avg = sum(len(d) for d in self.docs) / self.n or 1.0
        self.vecs = np.vstack([self._vectorise(d) for d in self.docs]) if chunks else np.zeros((0, DIM))

    def _idf(self, t: str) -> float:
        return math.log(1 + (self.n - self.df.get(t, 0) + 0.5) / (self.df.get(t, 0) + 0.5))

    def _vectorise(self, tokens: list[str]) -> np.ndarray:
        v = np.zeros(DIM)
        for t, c in Counter(tokens).items():
            v[zlib.crc32(t.encode()) % DIM] += (1 + math.log(c)) * self._idf(t)  # a stable hash, so results are reproducible
        n = np.linalg.norm(v)
        return v / n if n else v

    def _bm25(self, q: list[str]) -> np.ndarray:
        scores = np.zeros(len(self.docs))
        for i, d in enumerate(self.docs):
            tf = Counter(d)
            for t in q:
                if t in tf:
                    scores[i] += self._idf(t) * tf[t] * 2.5 / (tf[t] + 1.5 * (0.25 + 0.75 * len(d) / self.avg))
        return scores

    def search(self, query: str, k: int = 5, where=None) -> list[Hit]:
        if not self.chunks:
            return []
        q = tokenize(rewrite_query(query))
        if not q:
            return []
        bm = self._bm25(q)
        vec = self.vecs @ self._vectorise(q)
        allowed = [i for i, c in enumerate(self.chunks) if where is None or where(c)]
        # reciprocal rank fusion of the two rankings
        fused: dict[int, float] = {}
        for ranking in (sorted(allowed, key=lambda i: -bm[i]), sorted(allowed, key=lambda i: -vec[i])):
            for rank, i in enumerate(ranking[:50]):
                if bm[i] > 0 or vec[i] > 0.05:
                    fused[i] = fused.get(i, 0) + 1 / (60 + rank + 1)
        # rerank: reward chunks that contain every query term, and exact phrases
        qset, lowq = set(q), query.lower()
        for i in list(fused):
            present = qset & set(self.docs[i])
            fused[i] += 0.02 * len(present) / len(qset) + (0.02 if len(present) == len(qset) else 0)
            if any(w in self.chunks[i].text.lower() for w in re.findall(r"[a-z0-9+#]{4,}", lowq)):
                fused[i] += 0.005
        top = sorted(fused, key=lambda i: -fused[i])[:k]
        return [Hit(self.chunks[i], round(fused[i], 4), f"bm25={bm[i]:.2f} vec={vec[i]:.2f}") for i in top]


# ---- indexes -------------------------------------------------------------------------------------------------------------
def cv_chunks(db, requisition_id: int | None = None) -> list[Chunk]:
    """Sections of every candidate's BLIND record (title, each job, skills, certifications, education)."""
    from sqlalchemy import select

    from app.models import Candidate
    from app.privacy import make_blind

    q = select(Candidate).where(Candidate.stage.notin_(["APPLIED", "WITHDRAWN"]))
    if requisition_id:
        q = q.where(Candidate.requisition_id == requisition_id)
    chunks = []
    for c in db.scalars(q):
        b = make_blind(c)
        parts = ([("Title", b.current_title)] if b.current_title else []) + [("Experience", j) for j in b.jobs]
        parts += [("Skills", ", ".join(b.skills))] if b.skills else []
        parts += [("Certification", x) for x in b.certifications] + ([("Education", b.education)] if b.education else [])
        for n, (section, text) in enumerate(parts):
            chunks.append(Chunk(f"cv{c.id}-{n}", "cv", str(c.id), section, text, {"stage": c.stage}))
    return chunks


def policy_chunks() -> list[Chunk]:
    path = Path(get_settings().kit_dir) / "hiring_policy.md"
    if not path.exists():
        return []
    chunks, section = [], ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        m = re.match(r"^(\d+\.\d+)\s+(.*)", line)
        if m:
            chunks.append(Chunk(f"pol{m.group(1)}", "policy", m.group(1), section, m.group(2)))
    return chunks


def question_chunks() -> list[Chunk]:
    import json

    path = Path(get_settings().kit_dir) / "question_bank.json"
    if not path.exists():
        return []
    return [Chunk(f"q{q['id']}", "question", q["id"], q["skill"], q["question"] + " " + " ".join(q.get("key_points", []))) for q in json.loads(path.read_text(encoding="utf-8"))]


_policy_index: HybridIndex | None = None


def policy_index() -> HybridIndex:
    global _policy_index
    if _policy_index is None:
        _policy_index = HybridIndex(policy_chunks())
    return _policy_index


def format_source(c: Chunk) -> str:
    if c.source == "cv":
        return f"Candidate #{c.ref} · {c.section}"
    if c.source == "policy":
        return f"Hiring policy §{c.ref} ({c.section})"
    return f"Question {c.ref} ({c.section})"


# ---- tools (the Screening and Assistant agents may call these) -------------------------------------------------------------------
from pydantic import BaseModel  # noqa: E402


class SearchArgs(BaseModel):
    query: str
    k: int = 5
    requisition_id: int | None = None


@register_tool("search_cvs", SearchArgs, "Hybrid keyword + vector search over the blind sections of the CV pool")
def search_cvs(args: SearchArgs, ctx: dict) -> list[dict]:
    idx = HybridIndex(cv_chunks(ctx["db"], args.requisition_id))
    return [{"candidate_id": int(h.chunk.ref), "section": h.chunk.section, "text": h.chunk.text, "score": h.score,
             "source": format_source(h.chunk)} for h in idx.search(args.query, args.k)]


@register_tool("search_policy", SearchArgs, "Search the hiring policy")
def search_policy(args: SearchArgs, ctx: dict) -> list[dict]:
    return [{"section": h.chunk.ref, "text": h.chunk.text, "score": h.score, "source": format_source(h.chunk)} for h in policy_index().search(args.query, args.k)]
