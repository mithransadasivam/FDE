"""Day 18: the chatbot's model card, kept as data (governance/model_card.json) and shown as a page.

A model card is a short, honest description of an AI system for the people who use it, run it and
approve it: what it is for, what it is not for, what it was tested on and how well it did, where it
fails, and who watches it. Keeping it as JSON next to the code means a test can check it is
complete and that every result points to real evidence.

Done: REQUIRED, render_markdown().
Activity 3: fill in card_gaps(). Check it with tests/test_model_card.py.
"""

from pathlib import Path

REQUIRED = [
    "name",
    "version",
    "owner",
    "purpose",
    "intended_users",
    "out_of_scope",
    "models",
    "data",
    "evaluation",
    "limitations",
    "human_oversight",
    "risk_category",
    "contact",
]
MIN_LIMITATIONS = 3


def empty(value) -> bool:
    """True for a missing value: None, "", [], {} or text that is only spaces or "TODO"."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == "" or value.strip().upper().startswith("TODO")
    return len(value) == 0


def card_gaps(card: dict, root: str = ".") -> list[str]:
    """TODO (Activity 3): everything that stops this model card being complete.

    Rules (tests/test_model_card.py checks each one). Collect, in this order:
    1. for each key in REQUIRED, in order, where empty(card.get(key)):  f"missing: {key}"
    2. for each entry in card.get("evaluation") or [] (each a dict with "metric", "value", "source"):
       - "metric", "value" or "source" empty    -> f"evaluation {n}: needs metric, value and source"
         (n counts from 1)
       - otherwise, Path(root, entry["source"]) does not exist
                                                 -> f"evaluation {n}: no evidence at {entry['source']}"
    3. fewer than MIN_LIMITATIONS limitations (but not empty: that is rule 1)
                                                 -> f"limitations: at least {MIN_LIMITATIONS}"
    An empty list means the card is complete.
    """
    raise NotImplementedError("TODO (Activity 3)")


def render_markdown(card: dict, gaps: list[str] | None = None) -> str:
    """The model card as a page: governance/MODEL_CARD.md."""

    def items(value):
        if isinstance(value, list):
            return "\n".join(f"- {v}" for v in value) or "- (none)"
        return str(value or "(missing)")

    out = [
        f"# Model card: {card.get('name', '(no name)')}",
        "",
        (
            f"Version {card.get('version', '?')} · Owner: {card.get('owner', '?')} · "
            f"EU AI Act category: {card.get('risk_category', '?')}"
        ),
        "",
    ]
    for title, key in [
        ("Purpose", "purpose"),
        ("Intended users", "intended_users"),
        ("Out of scope", "out_of_scope"),
        ("Models", "models"),
        ("Data", "data"),
    ]:
        out += [f"## {title}", "", items(card.get(key)), ""]
    out += ["## Evaluation", "", "| Metric | Result | Evidence |", "|---|---|---|"]
    for e in card.get("evaluation") or []:
        out.append(
            f"| {e.get('metric', '')} | {e.get('value', '')} | {e.get('source', '')} |"
        )
    out += [
        "",
        "## Limitations",
        "",
        items(card.get("limitations")),
        "",
        "## Human oversight",
        "",
        items(card.get("human_oversight")),
        "",
        "## Contact",
        "",
        items(card.get("contact")),
        "",
    ]
    if gaps:
        out += ["## Gaps (this card is not complete)", "", items(gaps), ""]
    return "\n".join(out)
