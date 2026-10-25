"""A small BM25 index over the policy clauses, runbook steps, service catalogue, on-call names and past incidents.

The index is built from the catalogue, which never contains `oncall_private`, so a personal mobile cannot be retrieved.
Every chunk has a source label the answer can cite: 'policy 5.3', 'RB-04 step 2', 'services db-core', 'INC-2291'.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from .catalog import Catalog

_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_STOP = {"the", "a", "an", "of", "to", "is", "are", "in", "on", "and", "or", "for", "what", "which", "do", "does", "it", "i", "how",
         "this", "that", "be", "by", "with", "at", "as", "we", "you", "can", "should", "there", "if", "from"}


def tokens(text: str) -> list[str]:
    out = []
    for t in _TOKEN.findall(text.lower()):
        if t in _STOP:
            continue
        out.append(t)
        if "-" in t:
            out.extend(p for p in t.split("-") if p and p not in _STOP)
    return out


class Index:
    def __init__(self, cat: Catalog):
        self.cat = cat
        self.chunks: list[dict] = []
        self._build()
        self.df: Counter = Counter()
        self.tf: list[Counter] = []
        for c in self.chunks:
            toks = tokens(c["source"] + " " + c["text"])
            self.tf.append(Counter(toks))
            self.df.update(set(toks))
        self.avg = sum(sum(t.values()) for t in self.tf) / max(len(self.tf), 1)

    def _build(self) -> None:
        cat = self.cat
        for cl in cat.clauses:
            self.chunks.append({"source": f"policy {cl.clause_id}", "text": cl.text, "kind": "policy"})
        for rb in cat.runbooks.values():
            self.chunks.append({"source": rb.runbook_id, "kind": "runbook",
                                "text": f"{rb.title}. Used for: {', '.join(rb.used_for)}. "
                                        f"Steps: " + "; ".join(f"{s.no} [{s.kind}] {s.tool}" for s in rb.steps)})
            for s in rb.steps:
                need = "needs approval (policy 5)" if s.kind == "CHANGE" else "may run without approval"
                self.chunks.append({"source": f"{rb.runbook_id} step {s.no}", "kind": "runbook",
                                    "text": f"{rb.title}. Step {s.no} [{s.kind}] {s.tool}: {s.text} This step {need}."})
        for sv in cat.services.values():
            dep = ", ".join(sv.depends_on) or "nothing"
            users = ", ".join(cat.direct_dependants(sv.service_id)) or "nothing"
            self.chunks.append({"source": f"services {sv.service_id}", "kind": "service",
                                "text": f"{sv.service_id} ({sv.name}) is tier {sv.tier}, owned by {sv.owner_team}; depends on {dep}; "
                                        f"depended on by {users}; runbooks {', '.join(sv.runbooks)}."})
        for team, p in cat.oncall.items():
            self.chunks.append({"source": f"oncall {team}", "kind": "oncall",
                                "text": f"{team} on-call engineer is {p['engineer']} ({p['work_email']}). Contact the team with page_oncall."})
        for h in cat.history:
            self.chunks.append({"source": h["incident_id"], "kind": "past",
                                "text": f"Past incident {h['incident_id']} on {h['service']}: {h['symptom']}, {h['severity']}, root cause "
                                        f"{h['root_cause_service']}, fixed by {h['fixed_by']} in {h['minutes_to_resolve']} minutes. {h['notes']}"})

    def size(self) -> int:
        return len(self.chunks)

    def search(self, question: str, k: int = 6, extra: list[dict] | None = None) -> list[dict]:
        pool = list(zip(self.chunks, self.tf))
        if extra:
            for c in extra:
                pool.append((c, Counter(tokens(c["source"] + " " + c["text"]))))
        q = tokens(question)
        n = len(pool)
        rb_ids = {m.upper().replace("RB", "RB-") if "-" not in m else m.upper() for m in re.findall(r"\brb-?\d{2}\b", question, re.I)}
        clauses = set(re.findall(r"\b\d\.\d\b", question))
        services = set(self.cat.find_services(question))
        scored = []
        for c, tf in pool:
            dl = sum(tf.values()) or 1
            s = 0.0
            for term in q:
                if term in tf:
                    df = self.df.get(term, 0) or 1
                    idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                    s += idf * tf[term] * 2.5 / (tf[term] + 1.5 * (0.25 + 0.75 * dl / self.avg))
            src = c["source"]
            if any(src.startswith(r) for r in rb_ids):
                s += 6
            if src.startswith("policy ") and src[7:] in clauses:
                s += 6
            if any(sv in c["text"].split() or src.endswith(sv) for sv in services):
                s += 1.5
            scored.append((s, c))
        scored.sort(key=lambda x: -x[0])
        return [c for s, c in scored[:k] if s > 0]
