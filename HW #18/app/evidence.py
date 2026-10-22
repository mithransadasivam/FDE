"""Day 18: collect the evidence from earlier labs into governance/evidence/, with a manifest.

An auditor asks "show me": the evaluation results, the red-team report, the bias test. Results in
logs/ are not committed and change with every run, so the governance pack points to dated copies
that are committed, each with a fingerprint (SHA-256) that shows it was not edited afterwards.

Done: nothing to fill in.
"""

import hashlib
import shutil
from datetime import date
from pathlib import Path

EVIDENCE_DIR = "governance/evidence"
# (file name in the evidence folder, where a lab writes it, the command that makes it)
SOURCES = [
    (
        "quality_report.json",
        "data/quality_report.json",
        "python -m scripts.quality_gate (Day 8)",
    ),
    (
        "load_after.json",
        "logs/load_after.json",
        "python -m scripts.load_test --label after (Day 16)",
    ),
    (
        "red_team_before.json",
        "logs/red_team_before.json",
        "python -m scripts.red_team --label before (Day 17)",
    ),
    (
        "red_team_after.json",
        "logs/red_team_after.json",
        "python -m scripts.red_team --label after --guardrails --profile least (Day 17)",
    ),
    (
        "bias_report.json",
        "logs/bias_report.json",
        "python -m scripts.bias_test (Day 18)",
    ),
]


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def collect(root: str = ".", out: str = EVIDENCE_DIR, today: str | None = None) -> dict:
    """Copy each source that exists; write MANIFEST.md. Returns {"copied": [...], "missing": [...]}."""
    root_path, out_path = Path(root), Path(root) / out
    out_path.mkdir(parents=True, exist_ok=True)
    today = today or date.today().isoformat()  # noqa: DTZ011  (a local date is right here)
    copied, missing = [], []
    rows = [
        "# Evidence manifest",
        "",
        f"Collected on {today} by scripts/collect_evidence.py.",
        "",
        "| File | Copied from | SHA-256 (first 16) | How to make it again |",
        "|---|---|---|---|",
    ]
    for name, src, how in SOURCES:
        source = root_path / src
        if source.exists():
            shutil.copy(source, out_path / name)
            rows.append(f"| {name} | {src} | {fingerprint(out_path / name)} | {how} |")
            copied.append(name)
        elif (out_path / name).exists():
            rows.append(
                f"| {name} | (kept from an earlier collection) | {fingerprint(out_path / name)} | {how} |"
            )
            copied.append(name)
        else:
            rows.append(f"| {name} | MISSING | - | {how} |")
            missing.append((name, how))
    (out_path / "MANIFEST.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return {"copied": copied, "missing": missing}
