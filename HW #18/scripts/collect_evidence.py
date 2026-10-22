"""Day 18: copy the evidence from earlier labs into governance/evidence/ and write its manifest.

python -m scripts.collect_evidence

A missing file is listed with the command that makes it. Commit governance/evidence/: unlike logs/,
it is part of the record.
"""

from app.evidence import EVIDENCE_DIR, collect


def main():
    r = collect()
    for name in r["copied"]:
        print(f"  ok       {EVIDENCE_DIR}/{name}")
    for name, how in r["missing"]:
        print(f"  MISSING  {name:22} make it with: {how}")
    print(f"\nWrote {EVIDENCE_DIR}/MANIFEST.md")


if __name__ == "__main__":
    main()
