"""Checks the governance pack (Day 4, BR-18). Run after python -m scripts.build_governance.

    python -m scripts.governance_check        (writes evidence/governance_check.json; exit 1 if anything fails)

It checks that: all documents exist; the classification names Annex III point 4 and Article 5(1)(f); the risk register has at least 10 risks, each with an owner,
a control, an evidence file and a review date, covering all four NIST AI RMF functions; every number in the model card that cites an evidence file equals the value
in that file; every evidence file matches its SHA-256 hash in the manifest; the candidate notice contains what the law and the policy require; the accent
findings are in the risk register; and the model card lists the recordings it holds.
"""
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

GOV = Path("governance")
REQUIRED = ["classification.md", "model_card.md", "risk_register.csv", "risk_register.md", "candidate_notice.md", "explanation_template.md", "evidence/manifest.json"]
NIST = {"Govern", "Map", "Measure", "Manage"}
CITE = re.compile(r"(?P<val>-?\$?[\d.]+)\s*(?:%| s| of 5| of 20)?\s*\[evidence: (?P<file>[\w.\-]+)#(?P<path>[\w.]+)\]")


def dig(obj, path: str):
    for part in path.split("."):
        obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    return obj


def num(x) -> float:
    return float(str(x).replace("$", "").replace("%", "").strip())


def check() -> dict:
    results: list[dict] = []

    def ok(name: str, passed: bool, detail: str = "") -> None:
        results.append({"check": name, "passed": bool(passed), "detail": detail})

    missing = [f for f in REQUIRED if not (GOV / f).exists()]
    ok("all governance documents exist", not missing, ", ".join(missing) or f"{len(REQUIRED)} files")
    if missing:
        return {"passed": False, "checks": results}

    cls = (GOV / "classification.md").read_text(encoding="utf-8")
    ok("classification: high risk, Annex III point 4", "Annex III" in cls and "point 4" in cls and "HIGH RISK" in cls)
    ok("classification: prohibited practices (Art. 5(1)(f) emotion recognition)", "5(1)(f)" in cls)
    ok("classification: names the obligations (Art. 9, 12, 14, 15)", all(a in cls for a in ("Art. 9", "Art. 12", "Art. 14", "Art. 15")))

    with (GOV / "risk_register.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    ok("risk register has at least 10 risks", len(rows) >= 10, f"{len(rows)} risks")
    incomplete = [r["id"] for r in rows if not all((r.get(k) or "").strip() for k in ("risk", "nist_function", "owner", "control", "evidence", "review_date"))]
    ok("every risk has an owner, a control, an evidence file and a review date", not incomplete, ", ".join(incomplete))
    ok("risks cover all four NIST AI RMF functions", NIST <= {r["nist_function"] for r in rows}, ", ".join(sorted({r["nist_function"] for r in rows})))
    bad_ev = [r["id"] for r in rows if not (GOV / "evidence" / r["evidence"]).exists()]
    ok("every risk points to an evidence file that exists", not bad_ev, ", ".join(bad_ev))

    manifest = json.loads((GOV / "evidence" / "manifest.json").read_text(encoding="utf-8"))
    bad_hash = [n for n, h in manifest["files"].items() if not (GOV / "evidence" / n).exists() or hashlib.sha256((GOV / "evidence" / n).read_bytes()).hexdigest() != h]
    ok("every evidence file matches its hash in the manifest", not bad_hash and len(manifest["files"]) >= 8, f"{len(manifest['files'])} files; mismatches: {', '.join(bad_hash) or 'none'}")

    card = (GOV / "model_card.md").read_text(encoding="utf-8")
    cites = list(CITE.finditer(card))
    wrong = []
    for m in cites:
        try:
            actual = dig(json.loads((GOV / "evidence" / m["file"]).read_text(encoding="utf-8")), m["path"])
            if abs(num(actual) - num(m["val"])) > 1e-6:
                wrong.append(f"{m['file']}#{m['path']}: card says {m['val']}, file says {actual}")
        except Exception as e:
            wrong.append(f"{m['file']}#{m['path']}: {type(e).__name__}")
    ok("every number in the model card points to evidence and matches it", len(cites) >= 10 and not wrong, f"{len(cites)} cited numbers; " + ("; ".join(wrong) or "all match"))
    ok("model card states the mode and the limitations", "fake models" in card.lower() and "Known limitations" in card)
    ok("model card lists the recordings it holds and their retention (rule 10)", "Recordings" in card and "6 months" in card and "never used to train" in card)

    notice = (GOV / "candidate_notice.md").read_text(encoding="utf-8").lower()
    ok("candidate notice: AI is used, what is recorded, how long, ask for a person",
       all(t in notice for t in ("ai interviewer", "recorded", "6 months", "ask for a person")))
    ok("candidate notice covers the copilot-assisted interview", "assistant" in notice and "without the assistant" in notice)
    ok("explanation template says a recruiter reviews it before it is sent", "recruiter reviews" in (GOV / "explanation_template.md").read_text(encoding="utf-8").lower())

    acc = json.loads((GOV / "evidence" / "bias_accents.json").read_text(encoding="utf-8"))
    reg = " ".join(r["risk"] + " " + r["control"] for r in rows).lower()
    ok("bias findings are in the risk register", ("transcription" in reg) and (not acc["findings"] or f"{len(acc['findings'])} finding" in reg), f"{len(acc['findings'])} accent finding(s) logged")
    ok("bias tests (screening and accents) have run", (GOV / "evidence" / "bias_screening.json").exists() and (GOV / "evidence" / "bias_accents.json").exists())
    return {"passed": all(r["passed"] for r in results), "checks": results}


def main() -> int:
    r = check()
    Path("evidence").mkdir(exist_ok=True)
    Path("evidence/governance_check.json").write_text(json.dumps(r, indent=1), encoding="utf-8")
    for c in r["checks"]:
        print(("PASS " if c["passed"] else "FAIL ") + c["check"] + (f"  ({c['detail']})" if c["detail"] else ""))
    print("\nGovernance check: " + ("PASS" if r["passed"] else "FAIL"))
    return 0 if r["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
