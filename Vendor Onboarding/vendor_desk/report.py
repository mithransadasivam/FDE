"""EVAL_REPORT.md is built from sections ('## Part 1 ...', '## Part 3 ...'); each script replaces only its own."""
import re
from pathlib import Path

from vendor_desk import config

HEADER = "# Evaluation report\n\nResults of running the 19 cases in `data/onboarding_cases.csv`. Each part is written by a script.\n"


def write_section(title: str, body: str, path: Path | None = None) -> None:
    path = path or config.ROOT / "EVAL_REPORT.md"
    text = path.read_text(encoding="utf-8") if path.exists() else HEADER
    parts = re.split(r"(?m)^(?=## )", text)
    head, sections = parts[0], {re.match(r"## (.*)", p).group(1): p for p in parts[1:]}
    sections[title] = f"## {title}\n\n{body.strip()}\n\n"
    order = sorted(sections, key=lambda t: ("(offline" in t, t))
    path.write_text(head.rstrip() + "\n\n" + "".join(sections[t] for t in order), encoding="utf-8")


def table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)
