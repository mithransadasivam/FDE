"""Builds the one-page discovery summary that goes back to the client."""

from datetime import date

from app.discovery.criteria import check_criterion
from app.discovery.models import Criterion, Finding, UseCase
from app.discovery.usecases import score_use_case

KIND_TITLES = {
    "pain_point": "Pain points",
    "requirement": "Requirements",
    "constraint": "Constraints",
    "open_question": "Open questions",
}


def build_summary(findings: list[Finding], criteria: list[Criterion], use_cases: list[UseCase]) -> str:
    lines = ["# Discovery summary: Kestrelmoor Bank, KYC onboarding", "", f"*Draft for client review, {date.today():%d %B %Y}.*", ""]
    kept = [f for f in findings if f.review != "wrong" and f.evidence_ok is not False]
    for kind, title in KIND_TITLES.items():
        items = [f for f in kept if f.kind == kind]
        if items:
            lines += [f"## {title}", ""]
            lines += [f"- **{f.title}{'' if f.title[-1] in '.?!' else '.'}** {f.detail} ({f.speaker}: \"{f.quote}\")" for f in items]
            lines.append("")
    lines += ["## Success criteria", "", "| Criterion | Baseline | Target | Measured by | Owner | By |", "|---|---|---|---|---|---|"]
    for c in criteria:
        try:
            measurable = not check_criterion(c)
        except NotImplementedError:  # ENG-102 not built yet
            measurable = False
        if measurable:
            base = "–" if c.baseline is None else f"{c.baseline:g} {c.unit}"
            lines.append(f"| {c.metric} | {base} | {c.target:g} {c.unit} | {c.measured_how} | {c.owner} | {c.by_when} |")
    first = [u for u in use_cases if u.first_choice]
    lines += ["", "## First use case", ""]
    if first:
        u = first[0]
        lines.append(f"**{u.name}** (score {score_use_case(u):g}/100): {u.description}.")
    else:
        lines.append("Not chosen yet.")
    out = [u for u in use_cases if u.excluded_reason]
    if out:
        lines += ["", "Out of scope: " + "; ".join(f"{u.name} ({u.excluded_reason})" for u in out) + "."]
    return "\n".join(lines) + "\n"
