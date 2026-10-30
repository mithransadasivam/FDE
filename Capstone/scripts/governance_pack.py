"""The governance pack for the EU AI Act, built from real evidence (Day 4, prompt 8).

    python -m scripts.governance_pack                run the tests the risk register cites, then write governance/
    python -m scripts.governance_pack --full         run the WHOLE test suite instead (about 15 minutes) and put its summary in evidence.md
    python -m scripts.governance_pack --skip-tests   reuse the last test run (governance/test_run.json)
    python -m scripts.governance_pack --allow-gaps   list a missing or old report as "not yet tested" instead of stopping

It writes classification.md, model_card.md, risk_register.md (and .csv), evidence.md, oversight.md and one combined governance_pack.html. Everything is read from the
code, the settings, the database and reports/ : the only text written by hand is the description of each risk. The pack STOPS with a clear message if a required report is
missing or older than 7 days, or if a risk names a control (file and function) or a test that does not exist: a pack that quietly fills the gap is worse than none.
"""
import argparse
import ast
import html
import json
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select

GOV = Path("governance")
REPORTS = Path("reports")
MAX_AGE_DAYS = 7
REQUIRED_REPORTS = [("identity_swap", "Identity swap test", "python -m evals.identity_swap"), ("accent_test", "Accent test", "python -m evals.accent_test"),
                    ("copilot_eval", "Copilot evaluation", "python -m evals.copilot_eval"), ("cost_and_speed", "Cost and speed", "python -m scripts.cost_report"),
                    ("journey", "The whole journey", "python -m scripts.journey --fake"), ("attack_report", "Attack tests", "python -m scripts.attack_report")]

# ---- the risks: the only text written by hand. Each names the control in the code (file and function) and the test(s) that prove it. -------------------------------------
NEW = [  # risks added on Day 4 (the older ones come from scripts/build_governance.py and are given their control and tests below)
    ("R-019", "A forbidden question (children, age, family plans) is asked and the answer is used", "Manage", "medium", "high", "Voice & interviews lead",
     "The copilot warns within seconds, offers a better question and excludes the answer from scoring", "copilot_eval.json"),
    ("R-020", "Recruiters over-rely on the AI's scores and stop forming their own view", "Govern", "high", "medium", "Trust & quality lead",
     "The recruiter enters their own levels before any audio is shown; the AI's suggestion is shown beside the person's level, and a gap of 2 or more needs a reason", "journey.json"),
    ("R-021", "A CV is read wrongly (a field extracted incorrectly) and the candidate is scored on the wrong facts", "Measure", "medium", "high", "Intake & screening lead",
     "Unsure fields go to a review queue for a person; every score quotes the CV and the quote is checked by code", "eval_extraction.json"),
    ("R-022", "The hiring manager's blind view shows who the candidate is (a name inside a flag, a quote or a title)", "Manage", "low", "high", "Trust & quality lead",
     "Identity strings are hidden wherever text about a candidate is shown to a person who must not see it, and the journey checks the blind scorecard", "journey.json"),
]
CONTROLS = {  # id -> (file, function, [tests], report or None)
    "R-001": ("app/privacy.py", "make_blind", ["tests/test_identity_swap.py::test_the_pipeline_scores_every_variant_the_same_and_keeps_the_must_haves",
                                               "tests/test_screening.py::test_no_name_email_phone_address_or_dob_reaches_a_scoring_prompt"], "identity_swap"),
    "R-002": ("evals/accent_test.py", "main", ["tests/test_accent_test.py::test_one_answer_spoken_two_ways_is_really_transcribed_and_scored"], "accent_test"),
    "R-003": ("app/security.py", "wrap_untrusted", ["tests/test_attacks.py::test_cv_attacks_change_no_score_and_no_stage_and_are_flagged",
                                                   "tests/test_attacks.py::test_with_wrapping_the_same_paraphrase_is_stopped", "tests/test_security.py::test_c027s_hidden_text_is_found_by_reading_the_pdf"], "attack_report"),
    "R-004": ("app/guardrails.py", "assistant_request_check", ["tests/test_assistant_mcp.py::test_private_data_instructions_and_protected_traits_are_refused_by_code",
                                                              "tests/test_assistant_mcp.py::test_the_database_itself_refuses_private_columns_even_for_raw_sql"], None),
    "R-005": ("app/evidence.py", "quote_exists", ["tests/test_screening.py::test_a_quote_that_is_not_in_the_cv_zeroes_the_score", "tests/test_copilot_compliance.py::test_a_planted_fake_quote_is_caught_and_the_score_is_sent_back"], None),
    "R-006": ("app/supervisor.py", "move", ["tests/test_supervisor.py::test_system_can_read_and_screen_but_cannot_shortlist", "tests/test_supervisor.py::test_no_code_outside_the_supervisor_sets_the_stage_directly"], None),
    "R-007": ("app/agents/interviewer.py", "score_text", ["tests/test_governance.py::test_scoring_functions_take_text_only", "tests/test_governance.py::test_no_code_in_the_project_analyses_voice_or_faces"], None),
    "R-008": ("scripts/purge_recordings.py", "purge", ["tests/test_candidate_rights.py::test_the_purge_clears_old_transcripts_and_cv_files_but_keeps_the_levels",
                                                       "tests/test_day2_recording.py::test_purge_deletes_old_audio_and_logs_each_file_and_keeps_recent_audio"], None),
    "R-009": ("scripts/quality_gate.py", "main", ["tests/test_day4.py::test_trust_tab_shows_the_quality_bar_costs_and_live_checks"], "cost_and_speed"),
    "R-010": ("app/web/interview.py", "acknowledge_notice", ["tests/test_day2_invitation.py::test_starting_without_the_consent_tick_is_refused_everywhere",
                                                            "tests/test_copilot_day3.py::test_the_copilot_needs_the_notice_before_it_starts"], None),
    "R-011": ("evals/common.py", "write_report", ["tests/test_accent_test.py::test_the_report_is_dated_and_says_what_it_used"], None),
    "R-012": ("scripts/make_fictional_kit.py", "main", ["tests/test_interview_sim.py::test_sample_interviews_are_labelled_sample_fictional_candidate_in_the_staff_pages"], None),
    "R-013": ("app/costing.py", "cost_numbers", ["tests/test_cost_speed.py::test_the_numbers_are_per_unit_from_the_logged_calls"], "cost_and_speed"),
    "R-014": ("app/timing.py", "finish", ["tests/test_cost_speed.py::test_a_simulated_interview_is_timed_step_by_step"], "cost_and_speed"),
    "R-015": ("app/integrations.py", "emit", ["tests/test_product_integrations.py::test_the_api_is_read_only_and_blind", "tests/test_product_integrations.py::test_webhooks_are_recorded_but_not_sent_unless_live"], None),
    "R-016": ("app/datarights.py", "delete_my_application", ["tests/test_candidate_rights.py::test_deleting_removes_every_file_and_personal_field",
                                                            "tests/test_candidate_rights.py::test_the_decision_log_keeps_only_an_anonymous_trail"], None),
    "R-017": ("app/web/interview.py", "_logged_recording", ["tests/test_day2_recording.py::test_staff_can_open_the_recording_and_every_opening_is_logged",
                                                            "tests/test_replay_room.py::test_the_replay_is_for_staff_only_and_every_opening_is_logged"], None),
    "R-018": ("app/agents/communications.py", "check_draft", ["tests/test_emails.py::test_a_draft_with_a_score_a_protected_detail_an_offer_or_a_wrong_link_is_rejected",
                                                              "tests/test_emails.py::test_nothing_reaches_outbox_sent_without_a_persons_approval"], None),
    "R-019": ("app/agents/copilot.py", "process_turn", ["tests/test_copilot_day3.py::test_the_rules_warn_at_once_with_a_better_question_and_the_answer_is_excluded_and_logged",
                                                        "tests/test_copilot_eval.py::test_every_planned_moment_is_caught_and_the_warning_is_fast"], "copilot_eval"),
    "R-020": ("app/web/interview.py", "save_review", ["tests/test_replay_room.py::test_the_replay_needs_the_persons_own_review_first",
                                                      "tests/test_copilot_day3.py::test_the_decision_needs_the_recruiters_own_scores_and_a_reason_and_goes_through_the_supervisor"], "journey"),
    "R-021": ("app/web/candidates.py", "review_confirm", ["tests/test_review_privacy.py::test_confirm_needs_everything_checked_then_moves_to_extracted",
                                                         "tests/test_screening.py::test_every_score_has_a_verified_quote_that_is_really_in_the_cv"], None),
    "R-022": ("app/privacy.py", "redact_identity", ["tests/test_journey.py::test_a_flag_that_quotes_the_pdf_title_does_not_leak_the_name_to_the_hiring_manager",
                                                    "tests/test_screening.py::test_hiring_manager_sees_a_blind_screening_page"], "journey"),
}


class PackError(Exception):
    pass


# ---- verifying that what the pack claims exists --------------------------------------------------------------------------------------------------
def defined_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def verify_controls(rows: list[dict]) -> list[str]:
    problems = []
    for r in rows:
        f = Path(r["control_file"])
        if not f.exists():
            problems.append(f"{r['id']}: the control file {r['control_file']} does not exist")
        elif r["control_function"] not in defined_names(f):
            problems.append(f"{r['id']}: {r['control_file']} has no function or class called {r['control_function']}")
        for t in r["tests"]:
            tf, _, name = t.partition("::")
            if not Path(tf).exists():
                problems.append(f"{r['id']}: the test file {tf} does not exist")
            elif name not in defined_names(Path(tf)):
                problems.append(f"{r['id']}: {tf} has no test called {name}")
        if not r["tests"]:
            problems.append(f"{r['id']}: no test is named for this risk")
    return problems


def load_reports(allow_gaps: bool) -> tuple[dict, list[dict]]:
    """The reports the pack needs. Missing or older than 7 days: stop (or, with --allow-gaps, list as not yet tested)."""
    reports, gaps = {}, []
    now = datetime.now(timezone.utc)
    for name, label, how in REQUIRED_REPORTS:
        p = REPORTS / f"{name}.json"
        if not p.exists():
            gaps.append({"name": name, "label": label, "why": "no report: not yet tested", "how": how})
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        age = (now - datetime.fromisoformat(doc["date"])).total_seconds() / 86400
        if age > MAX_AGE_DAYS:
            gaps.append({"name": name, "label": label, "why": f"the report is {age:.0f} days old (the limit is {MAX_AGE_DAYS})", "how": how})
            continue
        reports[name] = {**doc, "age_days": round(age, 1)}
    if gaps and not allow_gaps:
        raise PackError("The governance pack needs fresh evidence and will not fill the gap by hand:\n" + "\n".join(f"  - {g['label']}: {g['why']}. Run: {g['how']}" for g in gaps) +
                        "\n(Run the commands, or use --allow-gaps to list them in evidence.md as 'not yet tested'.)")
    return reports, gaps


# ---- the test run ---------------------------------------------------------------------------------------------------------------------------------
def run_tests(node_ids: list[str] | None) -> dict:
    """Runs the cited tests (or the whole suite) and returns each test's result and the pytest summary line."""
    xml = Path(tempfile.mkdtemp(prefix="gov_")) / "result.xml"
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}", *(node_ids or [])]
    print("Running " + (f"the {len(node_ids)} tests named for this check" if node_ids else "the whole test suite") + " ...")
    done = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    results = {}
    if xml.exists():
        for case in ET.parse(xml).getroot().iter("testcase"):
            node = f"{case.get('classname', '').replace('.', '/')}.py::{case.get('name')}"
            status = "FAIL" if case.find("failure") is not None or case.find("error") is not None else "SKIPPED" if case.find("skipped") is not None else "PASS"
            results[node] = status
    tail = [ln for ln in (done.stdout or "").splitlines() if ln.strip()]
    summary = next((ln for ln in reversed(tail) if re.search(r"\d+ (passed|failed)", ln)), tail[-1] if tail else "no output")
    return {"summary": summary.strip(" ="), "results": results, "full": not node_ids, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "exit_code": done.returncode}


def test_status(run: dict, node: str) -> str:
    found = [v for k, v in run["results"].items() if k == node or k.startswith(node + "[")]  # a parametrised test runs once per case
    if not found:
        return "not run"
    return "FAIL" if "FAIL" in found else "PASS" if all(v == "PASS" for v in found) else "SKIPPED"


# ---- reading the platform ----------------------------------------------------------------------------------------------------------------------------
def all_tools_and_agents() -> tuple[dict, dict, dict]:
    import app.main  # noqa: F401  (importing the app registers every tool)
    from app.agents.base import AGENT_TOOLS, STEP_LIMITS, TOOLS

    return AGENT_TOOLS, TOOLS, STEP_LIMITS


def models_by_agent() -> dict[str, list[str]]:
    from app.db import OpsSession, init_ops_db
    from app.models_ext import ModelCall

    init_ops_db()
    out: dict[str, set] = {}
    with OpsSession() as ops:
        for agent, task, tier, model in ops.execute(select(ModelCall.agent, ModelCall.task, ModelCall.tier, ModelCall.model).distinct()):
            if agent and agent not in ("voice", "speech"):
                out.setdefault(agent, set()).add(f"{model} ({tier}, for {task})")
    return {k: sorted(v) for k, v in out.items()}


def log_counts() -> dict:
    from app.db import SessionLocal, init_db
    from app.models import DecisionLog
    from app.models_ext import HumanInterview, HumanInterviewScore

    init_db()
    with SessionLocal() as db:
        c = lambda *conds: db.scalar(select(func.count()).select_from(DecisionLog).where(*conds)) or 0  # noqa: E731
        warnings = 0
        for h in db.scalars(select(HumanInterview)):
            warnings += sum(1 for e in (h.events or []) if e.get("kind") == "warning")
        overrides = sum(1 for s in db.scalars(select(HumanInterviewScore)) if s.ai_suggestion is not None and s.level != s.ai_suggestion)
        return {"entries": c(), "approvals": c(DecisionLog.action.like("%approved%")), "decisions": c(DecisionLog.action.like("final decision%")),
                "moves by a person": c(DecisionLog.action.like("move %"), DecisionLog.actor.like("%@%")),
                "moves by the system": c(DecisionLog.action.like("move %"), DecisionLog.actor == "system"),
                "copilot warnings (forbidden questions)": warnings, "overrides (the recruiter's level differs from the AI's suggestion)": overrides,
                "instructions ignored and flagged": c(DecisionLog.action.like("%ignored%")) + c(DecisionLog.action.like("hidden text%")),
                "deletions (candidates deleted their data or it was erased)": c(DecisionLog.action.in_(["candidate deleted their data", "personal data erased"])),
                "deletions after the retention period": c(DecisionLog.action.like("%after retention period%")) + c(DecisionLog.action.like("interview audio deleted")) + c(DecisionLog.action == "interview transcript deleted")}


def section(md: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", md, re.S | re.M)
    return m.group(1).strip() if m else ""


# ---- the documents ----------------------------------------------------------------------------------------------------------------------------------
def classification_md(reports: dict) -> str:
    import inspect

    from app.agents import interviewer
    from app.config import Settings
    from app.web.interview import NOTICE
    from scripts import build_governance as bg

    fields = list(Settings.model_fields)
    suspicious = [f for f in fields if re.search(r"camera|video|emotion|face|sentiment|biometric|tone", f, re.I)]
    banned = re.compile(r"\b(cv2|opencv|face_recognition|deepface|fer|dlib|emotion|sentiment|affect|"  # banned libraries and words:
                        r"librosa|parselmouth|opensmile)\b|getUserMedia\(\s*\{[^}]*video", re.I)
    hits, scanned = [], 0
    for p in list(Path("app").rglob("*.py")) + list(Path("templates").rglob("*.html")) + list(Path("static").glob("*.js")):
        text = p.read_text(encoding="utf-8", errors="ignore")
        scanned += 1
        for m in banned.finditer(text):
            line = text[:m.start()].count("\n") + 1
            context = text.splitlines()[line - 1].strip()
            if not re.search(r"no |not |never|without|banned|forbid|refus|test|# |\"\"\"|prohibit|tone, emotion", context, re.I):
                hits.append(f"{p}:{line}: {context[:100]}")
    sig = inspect.signature(interviewer.score_text)
    shots = sorted(Path("docs/screenshots").glob("*.png")) if Path("docs/screenshots").exists() else []
    notice_shot = next((s for s in shots if "interview" in s.name.lower() or "notice" in s.name.lower()), None)
    proof = f"""
## Proof that the platform does no emotion recognition (Article 5(1)(f)): read from the code and settings, not asserted

- **Settings.** The platform's settings (`app/config.py::Settings`) have {len(fields)} fields: {', '.join(f'`{f}`' for f in fields[:14])}, and more. Fields about a camera, video, emotion, face, sentiment, biometrics or tone: **{', '.join(suspicious) or 'none'}**.
- **Code.** {scanned} files (`app/**/*.py`, `templates/**/*.html`, `static/*.js`) were scanned for emotion, face, voice-analysis and camera code: **{len(hits)} match(es)**{'.' if not hits else ':'}
{chr(10).join('  - ' + h for h in hits)}
- **What scoring receives.** `app/agents/interviewer.py::score_text{sig}`: a question, the words said, whether a hint was used and an id. Not audio, not a recording, not a picture. (Test: `tests/test_governance.py::test_scoring_functions_take_text_only`.)
- **Camera.** The interview page asks only for the microphone (`getUserMedia({{audio: true}})`). No video is requested or stored.
"""
    notice = f"""
## Transparency to candidates (Article 50, Article 26(7))

The notice a candidate must read and acknowledge before the AI interview (`app/web/interview.py::NOTICE`, the same words the page shows):

> {NOTICE}

Screenshot: {('`' + str(notice_shot) + '`') if notice_shot else '`docs/screenshots/` has no interview-notice screenshot yet: run `python -m scripts.take_screenshots`'}.
"""
    base = bg.CLASSIFICATION
    return base.replace("## Obligations that follow", proof + notice + "\n## Obligations that follow", 1)


def model_card_md(reports: dict, gaps: list[dict]) -> str:
    from app.config import get_settings
    from scripts import build_governance as bg

    tools_by_agent, tools, steps = all_tools_and_agents()
    s = get_settings()
    used = models_by_agent()
    rows = []
    for agent, allowed in tools_by_agent.items():
        models = used.get(agent) or ["no model call logged yet"]
        rows.append(f"| {agent} | {'<br>'.join(models)} | {', '.join(f'`{t}`' for t in sorted(allowed))} | {steps.get(agent, '-')} |")
    every = sorted(tools)
    sections = []
    for agent, allowed in tools_by_agent.items():
        cannot = [t for t in every if t not in allowed]
        sensitive = [t for t in cannot if re.search(r"send|move|shortlist|decide|delete|approve|set_stage|write", t)]
        sections.append(f"**{agent}**: inputs and outputs are its tools: " + "; ".join(f"`{t}` ({(tools[t].description or '').rstrip('.')})" for t in sorted(allowed) if t in tools) +
                        f". It must never: call any of the other {len(cannot)} tools (refused by code in `app/agents/base.py`)" + (f", in particular {', '.join(f'`{t}`' for t in sensitive)}" if sensitive else "") + ".")
    limits = []
    for name, label, _ in REQUIRED_REPORTS:
        p = REPORTS / f"{name}.md"
        if p.exists() and name in reports:
            body = section(p.read_text(encoding="utf-8"), "Limits")
            if body:
                limits.append(f"**{label}** (`reports/{name}.md`):\n{body}")
    models_line = f"large `{s.large_model}`, small `{s.small_model}`, local `{s.local_model}`, fallback `{s.fallback_model}`, vision `{s.vision_model}`, speech to text `faster-whisper {s.whisper_model}`"
    extra = f"""

---
# Part 2: read from the settings, the code and the reports (generated {datetime.now(timezone.utc).date().isoformat()})

## Every agent, with its model, its inputs and outputs, and what it must never do
Models configured in `app/config.py`: {models_line}. Mode when this was built: **{'fake models' if s.fake_models else 'real models'}**.

| Agent | Models actually called (from the model-call log) | Tools it may call (the only inputs and outputs it has) | Step limit |
|---|---|---|---|
{chr(10).join(rows)}

{chr(10).join('- ' + x for x in sections)}

## Known limits, taken from the reports
{chr(10).join(limits) or 'No report has a Limits section yet.'}
{chr(10).join('- **Not yet tested:** ' + g['label'] + ' (' + g['why'] + ')' for g in gaps)}

## The human oversight points
Every point where a person decides is listed, from the supervisor's table, in `oversight.md`.
"""
    return bg.model_card() + extra


def risk_rows(run: dict, reports: dict) -> list[dict]:
    from scripts import build_governance as bg

    base = bg.risks()
    base += [dict(zip(("id", "risk", "nist_function", "likelihood", "impact", "owner", "control", "evidence"), r), review_date=bg.REVIEW) for r in NEW]
    rows = []
    for r in base:
        f, fn, tests, report = CONTROLS[r["id"]]
        statuses = [test_status(run, t) for t in tests]
        rep = reports.get(report) if report else None
        overall = "FAIL" if "FAIL" in statuses or (rep and not rep["passed"]) else ("PASS" if all(s == "PASS" for s in statuses) else "not fully run")
        r = {**r, "control_file": f, "control_function": fn, "tests": tests, "test_results": statuses, "report": report, "report_result": ("PASS" if rep and rep["passed"] else "FAIL" if rep else "-"),
             "latest_result": overall}
        if report:
            r["evidence"] = f"{report}.json"
        rows.append(r)
    return rows


def risk_register_md(rows: list[dict]) -> str:
    L = ["# Risk register", "", f"{len(rows)} risks. NIST AI RMF functions: Govern, Map, Measure, Manage. Every control is a file and a function that exist; every test is a test that exists and "
         "was run for this pack (see `evidence.md`). The risk descriptions are the only text written by hand.", "",
         "| Id | Risk | Function | Owner | Control in the code | Test that proves it | Latest result |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        tests = "<br>".join(f"`{t.split('::')[1]}` ({s})" for t, s in zip(r["tests"], r["test_results"]))
        rep = f"<br>report `{r['report']}`: {r['report_result']}" if r["report"] else ""
        L.append(f"| {r['id']} | {r['risk']} | {r['nist_function']} | {r['owner']} | `{r['control_file']}::{r['control_function']}` | {tests}{rep} | **{r['latest_result']}** |")
    return "\n".join(L) + "\n"


def evidence_md(reports: dict, gaps: list[dict], run: dict, rows: list[dict]) -> str:
    counts = log_counts()
    from app.config import get_settings

    L = ["# Evidence", "", f"Built {datetime.now(timezone.utc).isoformat(timespec='seconds')}. Mode: **{'fake models' if get_settings().fake_models else 'real models'}**. Database: `{get_settings().database_url}`.", "",
         "## Reports in reports/", "| Report | Date | Age (days) | Result | File |", "|---|---|---|---|---|"]
    for name, label, _ in REQUIRED_REPORTS:
        d = reports.get(name)
        L.append(f"| {label} | {d['date'][:10]} | {d['age_days']} | **{'PASS' if d['passed'] else 'FAIL'}** | `reports/{name}.md` |" if d else f"| {label} | - | - | **not yet tested** | - |")
    L += ["", "## The test run", f"{'The whole test suite' if run['full'] else 'The ' + str(len(run['results'])) + ' tests the risk register cites'}, run {run['at']}: **{run['summary']}**.", "",
          "| Test | Result |", "|---|---|", *[f"| `{k}` | {v} |" for k, v in sorted(run["results"].items())], ""]
    L += ["## Counts from the decision log", "| What | How many |", "|---|---|", *[f"| {k} | {v} |" for k, v in counts.items()], "",
          "## Anything not yet tested, said plainly"]
    plain = [f"- **{g['label']}**: {g['why']}. Run `{g['how']}`." for g in gaps]
    plain += [f"- Risk {r['id']} ({r['risk'][:70]}...): its tests did not all run." for r in rows if r["latest_result"] == "not fully run"]
    plain += ["- Every report except the real-model ones was produced with **fake models** where it says so: the figures show the platform works, not how good a real model is.",
              "- The accent test uses computer voices, not real people.", "- Real accented speech, real candidates and a real-model run have not been tested."]
    L += plain + [""]
    return "\n".join(L)


def oversight_md() -> str:
    from app.supervisor import ALLOWED, PERSON, SYSTEM

    person = [(a.value, b.value) for a, moves in ALLOWED.items() for b, who in moves.items() if who == PERSON]
    system = [(a.value, b.value) for a, moves in ALLOWED.items() for b, who in moves.items() if who == SYSTEM]
    other = [("An email reaches a candidate", "a person approves it in the outbox", "app/agents/communications.py", "approve_and_send"),
             ("A final decision is recorded", "a recruiter chooses, with a reason, after the evidence check was read", "app/decisions.py", "decide"),
             ("The evidence checker's problems", "a person acknowledges them before a shortlist or decision", "app/agents/checker.py", "acknowledge"),
             ("The AI interview scorecard", "the recruiter enters their own level for each must-have before any audio", "app/web/interview.py", "save_review"),
             ("The human interview", "the recruiter enters their own levels; the copilot only suggests", "app/web/copilot.py", "recruiter_scores"),
             ("A candidate's explanation", "a recruiter reviews the draft before it is sent", "app/decisions.py", "explain_not_shortlisted"),
             ("Erasure approved by the company", "a recruiter approves or refuses with a reason", "app/datarights.py", "erase")]
    bad = [f"{f}::{n}" for _, _, f, n in other if n not in defined_names(Path(f))]
    if bad:
        raise PackError("oversight.md names code that does not exist: " + ", ".join(bad))
    L = ["# Human oversight", "", "Read from `app/supervisor.py::ALLOWED`: every move marked as a person's decision cannot be made by the system (`move()` refuses it, tested in "
         "`tests/test_supervisor.py::test_table_every_decision_is_a_persons_and_only_early_steps_are_automatic`).", "",
         "## Moves only a person can make (with a reason)", "| From | To |", "|---|---|", *[f"| {a} | {b} |" for a, b in person], "",
         "## Automatic steps the system may take (never a decision about a person)", "| From | To |", "|---|---|", *[f"| {a} | {b} |" for a, b in system], "",
         "## Other points where a person decides", "| Point | Who decides, and how | Control |", "|---|---|---|", *[f"| {a} | {b} | `{f}::{n}` |" for a, b, f, n in other], ""]
    return "\n".join(L)


# ---- one combined HTML file ------------------------------------------------------------------------------------------------------------------------
def md_to_html(md: str) -> str:
    out, lines, i, in_list = [], md.splitlines(), 0, None

    def inline(t: str) -> str:
        t = html.escape(t, quote=False).replace("&lt;br&gt;", "<br>")
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        return re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", t)

    def close():
        nonlocal in_list
        if in_list:
            out.append(f"</{in_list}>")
            in_list = None

    while i < len(lines):
        ln = lines[i]
        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1]):
            close()
            head = [c.strip() for c in ln.strip("|").split("|")]
            out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>")
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                out.append("<tr>" + "".join(f"<td>{inline(c.strip())}</td>" for c in lines[i].strip().strip("|").split("|")) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue
        m = re.match(r"^(#{1,4}) (.*)", ln)
        if m:
            close()
            out.append(f"<h{len(m.group(1))}>{inline(m.group(2))}</h{len(m.group(1))}>")
        elif re.match(r"^\s*[-*] ", ln):
            if in_list != "ul":
                close()
                out.append("<ul>")
                in_list = "ul"
            out.append(f"<li>{inline(re.sub(r'^\s*[-*] ', '', ln))}</li>")
        elif ln.startswith(">"):
            close()
            out.append(f"<blockquote>{inline(ln.lstrip('> '))}</blockquote>")
        elif ln.strip() == "---":
            close()
            out.append("<hr>")
        elif ln.strip():
            close()
            out.append(f"<p>{inline(ln)}</p>")
        else:
            close()
        i += 1
    close()
    return "\n".join(out)


def combined_html(docs: list[tuple[str, str]]) -> str:
    nav = "".join(f'<a href="#{n}">{n}</a>' for n, _ in docs)
    body = "".join(f'<section id="{n}">{md_to_html(t)}</section>' for n, t in docs)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Governance pack</title>
<style>:root{{--bg:#fff;--ink:#14213d;--muted:#5b6478;--line:#d9deea;--accent:#4f46e5;--code:#f3f4fb}}@media(prefers-color-scheme:dark){{:root{{--bg:#0e1424;--ink:#e6eaf7;--muted:#9aa4bf;--line:#26304d;--accent:#8b8bff;--code:#171f38}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 system-ui,sans-serif}}nav{{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:.6rem 1rem;display:flex;gap:1rem;flex-wrap:wrap}}
nav a{{color:var(--accent);text-decoration:none;font-weight:600}}main{{max-width:1050px;margin:0 auto;padding:1rem 1rem 4rem}}section{{border-bottom:1px solid var(--line);padding-bottom:2rem}}table{{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.88rem}}
th,td{{border:1px solid var(--line);padding:.4rem .6rem;text-align:left;vertical-align:top}}th{{background:var(--code)}}code{{background:var(--code);padding:.05rem .3rem;border-radius:4px;font-size:.88em;word-break:break-word}}
blockquote{{border-left:4px solid var(--accent);margin:1rem 0;padding:.2rem 1rem;color:var(--muted)}}h1{{margin-top:2.5rem}}</style></head><body>
<nav><strong>Governance pack</strong>{nav}</nav><main>{body}</main></body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--skip-tests", action="store_true")
    ap.add_argument("--allow-gaps", action="store_true")
    args = ap.parse_args()
    from scripts import build_governance as bg

    try:
        reports, gaps = load_reports(args.allow_gaps)
        base = bg.risks() + [dict(zip(("id", "risk", "nist_function", "likelihood", "impact", "owner", "control", "evidence"), r), review_date=bg.REVIEW) for r in NEW]
        skeleton = [{"id": r["id"], "control_file": CONTROLS[r["id"]][0], "control_function": CONTROLS[r["id"]][1], "tests": CONTROLS[r["id"]][2]} for r in base]
        problems = verify_controls(skeleton)
        if problems:
            raise PackError("A risk names a control or test that does not exist:\n  - " + "\n  - ".join(problems))
        GOV.mkdir(exist_ok=True)
        if args.skip_tests:
            p = GOV / "test_run.json"
            if not p.exists():
                raise PackError("--skip-tests needs an earlier run (governance/test_run.json). Run once without it.")
            run = json.loads(p.read_text(encoding="utf-8"))
        else:
            ids = None if args.full else sorted({t for r in skeleton for t in r["tests"]})
            run = run_tests(ids)
            (GOV / "test_run.json").write_text(json.dumps(run, indent=1), encoding="utf-8")
        bg.main()  # the older files (candidate notice, explanation template, hashed evidence folder) and the baseline the new documents extend
        for name in reports:  # the reports go into the hashed evidence folder too
            (GOV / "evidence" / f"{name}.json").write_text((REPORTS / f"{name}.json").read_text(encoding="utf-8"), encoding="utf-8")
        manifest_path = GOV / "evidence" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        import hashlib

        for name in reports:
            manifest["files"][f"{name}.json"] = hashlib.sha256((GOV / "evidence" / f"{name}.json").read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        rows = risk_rows(run, reports)
        docs = {"classification.md": classification_md(reports), "model_card.md": model_card_md(reports, gaps), "risk_register.md": risk_register_md(rows),
                "evidence.md": evidence_md(reports, gaps, run, rows), "oversight.md": oversight_md()}
    except PackError as e:
        print("\nGOVERNANCE PACK NOT BUILT\n" + str(e))
        return 1
    for name, text in docs.items():
        (GOV / name).write_text(text, encoding="utf-8")
    import csv

    with (GOV / "risk_register.csv").open("w", newline="", encoding="utf-8") as f:
        fields = ["id", "risk", "nist_function", "likelihood", "impact", "owner", "control", "evidence", "review_date", "control_file", "control_function", "tests", "latest_result"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({**{k: r.get(k, "") for k in fields}, "control": f"{r['control']} [{r['control_file']}::{r['control_function']}]", "tests": " | ".join(r["tests"])})
    (GOV / "governance_pack.html").write_text(combined_html([(n[:-3], t) for n, t in docs.items()]), encoding="utf-8")
    failing = [r for r in rows if r["latest_result"] == "FAIL"]
    print(f"Governance pack written to governance/: {len(rows)} risks ({len(failing)} failing), {len(reports)} reports, {len(gaps)} gap(s); tests: {run['summary']}")
    for r in failing:
        print(f"  FAIL {r['id']}: {r['risk'][:80]}")
    print("Open governance/governance_pack.html")
    return 0 if not failing else 2


if __name__ == "__main__":
    sys.exit(main())
