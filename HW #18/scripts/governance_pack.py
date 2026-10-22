"""Day 18: build the governance pack: one page with everything a reviewer needs.

python -m scripts.governance_pack     (run collect_evidence, classify_use_cases and model_card first)

Writes governance/GOVERNANCE_PACK.md: the use-case inventory, the risks by NIST AI RMF function,
the bias test summary, the model card's status, the risk register and its checks.
Exit code 0 when the register and the model card pass their checks, 1 otherwise.
"""

import json
import sys
from datetime import date
from pathlib import Path

from app.model_card import card_gaps
from app.risk_register import FUNCTIONS, check_register, rating

REGISTER = "governance/risk_register.json"
CARD = "governance/model_card.json"
BIAS = "governance/evidence/bias_report.json"
OUT = "governance/GOVERNANCE_PACK.md"


def main():
    risks = json.loads(Path(REGISTER).read_text(encoding="utf-8"))
    card = json.loads(Path(CARD).read_text(encoding="utf-8"))
    problems, gaps = check_register(risks), card_gaps(card)
    lines = [
        f"# Governance pack: {card.get('name', '')}",
        "",
        (
            f"Built on {date.today().isoformat()} by scripts/governance_pack.py. "  # noqa: DTZ011
            f"Register: {'PASS' if not problems else 'FAIL'}. Model card: {'complete' if not gaps else 'gaps'}."
        ),
        "",
        "## 1. Use-case inventory (EU AI Act)",
        "",
        "See [use_case_inventory.md](use_case_inventory.md).",
        "",
        "## 2. Risks by NIST AI RMF function",
        "",
        "| Function | Risks | Open | Open and high |",
        "|---|---|---|---|",
    ]
    for f in FUNCTIONS:
        mine = [r for r in risks if r.get("function") == f]
        open_ = [r for r in mine if r.get("status") == "open"]
        high = [
            r["id"]
            for r in open_
            if rating(r["likelihood"], r["impact"])["level"] == "high"
        ]
        lines.append(f"| {f} | {len(mine)} | {len(open_)} | {', '.join(high) or '-'} |")
    lines += ["", "## 3. Bias test (counterfactual profiles)", ""]
    if Path(BIAS).exists():
        summary = json.loads(Path(BIAS).read_text(encoding="utf-8"))["summary"]
        lines += [
            "| Profile | Answers | Differed from baseline | Rate |",
            "|---|---|---|---|",
        ]
        lines += [
            f"| {p} | {s['answers']} | {s['differed']} | {s['rate']} |"
            for p, s in summary.items()
        ]
    else:
        lines.append(
            "No bias report in governance/evidence/: run scripts/bias_test.py, then scripts/collect_evidence.py."
        )
    lines += ["", "## 4. Model card", "", "See [MODEL_CARD.md](MODEL_CARD.md)."]
    lines += [f"- Gap: {g}" for g in gaps] or [
        "- Complete: every section filled, every result linked to evidence."
    ]
    lines += [
        "",
        "## 5. Risk register (highest score first)",
        "",
        "| Id | Risk | Function | Score | Owner | Status | Controls | Evidence |",
        "|---|---|---|---|---|---|---|---|",
    ]

    def score(r):
        try:
            return rating(r["likelihood"], r["impact"])["score"]
        except (KeyError, TypeError):
            return 0

    for r in sorted(risks, key=score, reverse=True):
        rt = (
            rating(r["likelihood"], r["impact"])
            if score(r)
            else {"score": "?", "level": "?"}
        )
        lines.append(
            f"| {r.get('id')} | {r.get('title')} | {r.get('function')} | {rt['score']} ({rt['level']}) | "
            f"{r.get('owner')} | {r.get('status')} | {'; '.join(r.get('controls') or [])} | "
            f"{', '.join(r.get('evidence') or [])} |"
        )
    lines += ["", "## 6. Checks", ""] + (
        [f"- {p}" for p in problems] or ["- The register passes every check."]
    )
    Path(OUT).write_text("\n".join(lines) + "\n", encoding="utf-8")
    for p in problems:
        print(f"  PROBLEM  {p}")
    for g in gaps:
        print(f"  GAP      {g}")
    print(
        f"\nRegister: {'PASS' if not problems else 'FAIL'} ({len(risks)} risks). "
        f"Model card: {'complete' if not gaps else f'{len(gaps)} gap(s)'}. Wrote {OUT}"
    )
    sys.exit(1 if problems or gaps else 0)


if __name__ == "__main__":
    main()
