"""The semantic layer: what the model is told about the warehouse (done, not a ticket).

semantic/caseflow_v1.yml, caseflow_v2.yml… one file per version. A version lists the approved tables and their columns,
how they join, a few metrics, example queries, and `terms`: the bank's own words ("turnaround", "backlog") with the
SQL that the bank means by them. render() turns a version into the text the model reads.
"""

import yaml

from app.config import SEMANTIC_DIR


def layers() -> list[str]:
    return sorted(p.stem for p in SEMANTIC_DIR.glob("caseflow_v*.yml"))


def load(name: str) -> dict:
    p = SEMANTIC_DIR / f"{name}.yml"
    if not p.exists():
        raise KeyError(f"No semantic layer {name}: expected semantic/{name}.yml")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    data.setdefault("terms", {})
    data["terms"] = data["terms"] or {}
    data.setdefault("examples", [])
    data["_name"] = name
    return data


def text(name: str) -> str:
    return (SEMANTIC_DIR / f"{name}.yml").read_text(encoding="utf-8")


def keys(layer: dict) -> set[str]:
    """The names of its terms and examples. The scripted model uses them to choose its reply (see agent.scripted_task)."""
    return set(layer.get("terms", {})) | {e.get("name", "") for e in layer.get("examples", [])} - {""}


def render(layer: dict) -> str:
    """The layer as the model reads it, in the system prompt."""
    out = [f"# The warehouse: {layer.get('description', '').strip()}", "", "## Conventions"]
    out += [f"- {c}" for c in layer.get("conventions", [])]
    out += ["", "## Tables (only these may be used)"]
    for t, spec in layer.get("tables", {}).items():
        out += ["", f"### {t}", spec.get("description", "").strip()]
        out += [f"- {c}: {d}" for c, d in spec.get("columns", {}).items()]
    out += ["", "## Joins"] + [f"- {j}" for j in layer.get("joins", [])]
    if layer.get("metrics"):
        out += ["", "## Metrics"]
        for m, spec in layer["metrics"].items():
            out += [f"- {m}: {spec.get('means', '').strip()} SQL: {' '.join(str(spec.get('sql', '')).split())}"]
    if layer.get("terms"):
        out += ["", "## The bank's terms: when a question uses one of these words (or a synonym), use exactly this meaning"]
        for t, spec in layer["terms"].items():
            syn = ", ".join(spec.get("synonyms", []))
            out += ["", f"### {t}" + (f" (also: {syn})" if syn else ""), str(spec.get("means", "")).strip()]
            if spec.get("sql"):
                out += ["SQL: " + " ".join(str(spec["sql"]).split())]
    if layer.get("examples"):
        out += ["", "## Example questions and queries"]
        for e in layer["examples"]:
            out += ["", f"Q: {e.get('question', '')}", "```sql", str(e.get("sql", "")).strip(), "```"]
    return "\n".join(out)
