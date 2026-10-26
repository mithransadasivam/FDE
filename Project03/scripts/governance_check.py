"""Governance you can check (Day 18).

    python -m scripts.governance_check            # collect the evidence, write the manifest, check the card and the register
    python -m scripts.governance_check --no-collect

Collects EVAL_REPORT.md, PERF_REPORT.md, SECURITY_FINDINGS.md and the red-team report into governance/evidence/ with a SHA-256
manifest, then checks that
  * the model card has no empty field and keeps every field of the template,
  * every number in the card's evaluation block appears in a report in governance/evidence/,
  * the risk register has at least six risks, each with a NIST AI RMF function, likelihood and impact, controls, an owner,
    a review date and evidence that exists (the named file is in the pack and contains the quoted text),
  * the manifest's hashes match the files.
Exit status 1 when anything fails, so it can sit in CI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

from tower.settings import ROOT

EVIDENCE_FILES = {  # file in the pack  <- where it is made
    "EVAL_REPORT.md": "EVAL_REPORT.md",
    "PERF_REPORT.md": "PERF_REPORT.md",
    "SECURITY_FINDINGS.md": "SECURITY_FINDINGS.md",
    "REDTEAM_REPORT.md": "reports/REDTEAM_REPORT.md",
    "CLASSIFICATION.md": "governance/classification.md",
}
NIST = {"GOVERN", "MAP", "MEASURE", "MANAGE"}
RISK_FIELDS = ["id", "risk", "nist_function", "likelihood", "impact", "controls", "evidence", "owner", "review_by", "status"]


def _lf(data: bytes) -> bytes:
    return data.replace(bytes([13, 10]), bytes([10]))  # CRLF to LF


def sha256(p: Path) -> str:
    """Hash with line endings normalised to LF, so the same file hashes the same on Windows, Linux and in a fresh clone."""
    return hashlib.sha256(_lf(p.read_bytes())).hexdigest()


def collect(root: Path) -> dict:
    ev = root / "governance" / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    manifest = {"algorithm": "sha256", "files": {}}
    for name, src in EVIDENCE_FILES.items():
        s = root / src
        if not s.exists():
            continue
        (ev / name).write_bytes(_lf(s.read_bytes()))
        manifest["files"][name] = {"sha256": sha256(ev / name), "bytes": (ev / name).stat().st_size, "source": src}
    (ev / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def empty_fields(obj, path: str = "") -> list[str]:
    """Paths of every empty value: '', [], {}, or None, however deeply nested."""
    out: list[str] = []
    if isinstance(obj, dict):
        if not obj:
            out.append(path or "(root)")
        for k, v in obj.items():
            out += empty_fields(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        if not obj:
            out.append(path)
        for i, v in enumerate(obj):
            out += empty_fields(v, f"{path}[{i}]")
    elif obj is None or (isinstance(obj, str) and not obj.strip()):
        out.append(path)
    return out


def template_keys(obj, path: str = "") -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(f"{path}.{k}" if path else k)
            keys |= template_keys(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
        for k, v in obj[0].items():
            keys.add(f"{path}[].{k}")
    return keys


def _evidence_text(ev: Path) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(ev.glob("*.md")))


_NUM = re.compile(r"\$\d+(?:\.\d+)?|\d+(?:\.\d+)?\s*/\s*\d+|\d+(?:\.\d+)?\s*(?:s|%)\b|\d+(?:\.\d+)?")


def numbers_in(text: str) -> list[str]:
    return [re.sub(r"\s+", "", m) for m in _NUM.findall(text)]


def check(root: Path = ROOT, do_collect: bool = True) -> list[str]:
    """Returns the list of problems. Empty means the governance pack passes."""
    errors: list[str] = []
    gov = root / "governance"
    ev = gov / "evidence"
    if do_collect:
        collect(root)
    # ---- manifest hashes
    mpath = ev / "MANIFEST.json"
    if not mpath.exists():
        errors.append("evidence: MANIFEST.json is missing")
        manifest = {"files": {}}
    else:
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
        for name in EVIDENCE_FILES:
            if name not in manifest["files"]:
                errors.append(f"evidence: {name} is not in the manifest")
        for name, meta in manifest["files"].items():
            f = ev / name
            if not f.exists():
                errors.append(f"evidence: {name} is listed in the manifest but missing")
            elif sha256(f) != meta["sha256"]:
                errors.append(f"evidence: {name} does not match its SHA-256 in the manifest")
    # ---- model card
    cp, tp = gov / "model_card.json", gov / "model_card_template.json"
    card = None
    if not cp.exists():
        errors.append("model card: governance/model_card.json is missing")
    else:
        card = json.loads(cp.read_text(encoding="utf-8"))
        errors += [f"model card: '{p}' is empty" for p in empty_fields(card)]
        if tp.exists():
            have = template_keys(card)
            errors += [f"model card: field '{k}' from the template is missing" for k in sorted(template_keys(json.loads(tp.read_text(encoding='utf-8'))) - have)]
        evid = _evidence_text(ev) if ev.exists() else ""
        evid_nums = set(numbers_in(evid))
        ev_block = card.get("evaluation", {})
        for key in ("scenarios_right", "runbook_steps_right", "attacks_stopped", "p95_seconds", "cost_per_1000_questions"):
            for n in numbers_in(str(ev_block.get(key, ""))):
                if n not in evid_nums:
                    errors.append(f"model card: number '{n}' in evaluation.{key} is not in any report in governance/evidence/")
        for rf in ev_block.get("report_files", []):
            if not (ev / rf).exists():
                errors.append(f"model card: report file '{rf}' is not in governance/evidence/")
    # ---- risk register
    rp = gov / "risk_register.json"
    if not rp.exists():
        errors.append("risk register: governance/risk_register.json is missing")
    else:
        risks = json.loads(rp.read_text(encoding="utf-8")).get("risks", [])
        if len(risks) < 6:
            errors.append(f"risk register: {len(risks)} risks, at least 6 are needed")
        ids = [r.get("id") for r in risks]
        if len(set(ids)) != len(ids):
            errors.append("risk register: duplicate risk ids")
        for r in risks:
            rid = r.get("id", "?")
            for f in RISK_FIELDS:
                if f not in r or r[f] in ("", [], None):
                    errors.append(f"risk {rid}: '{f}' is missing or empty")
            if r.get("nist_function") not in NIST:
                errors.append(f"risk {rid}: nist_function must be one of {sorted(NIST)}")
            for f in ("likelihood", "impact"):
                if not isinstance(r.get(f), int) or not 1 <= r[f] <= 5:
                    errors.append(f"risk {rid}: {f} must be a whole number from 1 to 5")
            try:
                date.fromisoformat(str(r.get("review_by", "")))
            except ValueError:
                errors.append(f"risk {rid}: review_by is not a date (YYYY-MM-DD)")
            for e in r.get("evidence", []):
                fname, _, quote = str(e).partition(":")
                fname, quote = fname.strip(), quote.strip()
                f = ev / fname
                if not f.exists():
                    errors.append(f"risk {rid}: evidence file '{fname}' is not in governance/evidence/")
                elif quote and quote.lower() not in f.read_text(encoding="utf-8").lower():
                    errors.append(f"risk {rid}: '{quote}' does not appear in {fname}")
    return errors


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-collect", action="store_true")
    a = ap.parse_args()
    errs = check(ROOT, not a.no_collect)
    if errs:
        print("GOVERNANCE CHECK: FAIL")
        for e in errs:
            print("  -", e)
        sys.exit(1)
    m = json.loads((ROOT / "governance" / "evidence" / "MANIFEST.json").read_text(encoding="utf-8"))
    risks = json.loads((ROOT / "governance" / "risk_register.json").read_text(encoding="utf-8"))["risks"]
    print("GOVERNANCE CHECK: PASS")
    print(f"  model card complete, {len(risks)} risks each with owner, review date and evidence")
    for n, meta in m["files"].items():
        print(f"  evidence {n}  sha256 {meta['sha256'][:16]}...")


if __name__ == "__main__":
    main()
