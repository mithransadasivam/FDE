"""Reads the client brief: the Markdown, plus the 'Key facts' list as label/value pairs."""

import re

from app.config import BRIEF_FILE


def load_brief() -> dict:
    md = BRIEF_FILE.read_text(encoding="utf-8")
    key = md.split("## Key facts", 1)[-1].split("\n## ", 1)[0]
    facts = [
        {"label": m.group(1), "value": m.group(2).strip()}
        for m in re.finditer(r"^- \*\*(.+?):\*\*\s*(.+)$", key, flags=re.M)
    ]
    return {"markdown": md, "facts": facts}
