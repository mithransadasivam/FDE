"""The final check (Day 4, prompt 9): is the repository clean, and is every requirement BR-01 to BR-20 backed by a test or a report that exists and passes?

    python -m scripts.final_check            runs the tests each requirement cites and reads the reports (a few minutes)
    python -m scripts.final_check --full     runs the WHOLE test suite and the journey first (about 20 minutes), then checks

Part 1, the repository: no .env or API key in the files or in the history, no real personal data (every e-mail address is a fictional one), no large model files, and .gitignore covers
data/, storage/ and the raw audio in reports/. Part 2, the requirements: each is OK only if every test it names exists and passed in this run and every report it names is fresh
and passed. Anything else is MISSING, and goes into the demo as a known gap. Nothing here is filled in from memory.
"""
import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path

from evals.common import load_report, table, write_report
from scripts.governance_pack import MAX_AGE_DAYS, run_tests

REQUIREMENTS = [  # id, what it asks for (from the project brief), tests that prove it, reports that prove it
    ("BR-01", "Voice note to job description and weighted rubric; biased wording flagged",
     ["tests/test_requisition.py::test_rubric_adds_to_100_and_every_skill_evidence_is_in_the_transcript", "tests/test_requisition.py::test_job_text_contains_no_biased_wording"], []),
    ("BR-02", "Read CVs in PDF, Word, scan and screenshot form; unclear fields go to review",
     ["tests/test_document.py::test_each_format_is_read_into_a_profile", "tests/test_review_privacy.py::test_review_queue_lists_the_unsure_fields"], []),
    ("BR-03", "Hide name, age, gender, photo, nationality and contact details before scoring",
     ["tests/test_screening.py::test_no_name_email_phone_address_or_dob_reaches_a_scoring_prompt", "tests/test_identity_swap.py::test_the_blind_record_drops_personal_circumstance_lines"], []),
    ("BR-04", "Set stages; stop for a person's approval before each move",
     ["tests/test_supervisor.py::test_system_can_read_and_screen_but_cannot_shortlist", "tests/test_supervisor.py::test_no_code_outside_the_supervisor_sets_the_stage_directly",
      "tests/test_supervisor_graph.py::test_nothing_passes_a_gate_without_a_person"], []),
    ("BR-05", "Score each skill with the exact CV sentence behind each score",
     ["tests/test_screening.py::test_every_score_has_a_verified_quote_that_is_really_in_the_cv", "tests/test_screening.py::test_a_quote_that_is_not_in_the_cv_zeroes_the_score"], []),
    ("BR-06", "A ranked shortlist with strengths and gaps, approved by the recruiter",
     ["tests/test_screening.py::test_shortlist_is_suggested_then_only_a_person_can_approve_it"], []),
    ("BR-07", "A first-round voice interview: spoken questions, diagrams, recorded and transcribed answers, follow-ups, each answer scored with a quote",
     ["tests/test_day2_interview_page.py::test_record_then_submit_saves_both_audio_files_and_transcribes", "tests/test_day2_diagrams.py::test_a_broken_diagram_is_retried_once_then_used_if_the_retry_is_good",
      "tests/test_day2_loop.py::test_a_weak_answer_is_followed_up_once_on_the_same_skill", "tests/test_day2_scorecard.py::test_the_scorecard_shows_levels_questions_with_why_quotes_and_the_summary"], []),
    ("BR-08", "Tell candidates AI is used before the interview; let them ask for a person",
     ["tests/test_day2_invitation.py::test_starting_without_the_consent_tick_is_refused_everywhere",
      "tests/test_day2_invitation.py::test_asking_for_a_person_is_logged_flagged_on_the_board_and_changes_no_score"], []),
    ("BR-09", "Answer recruiters' questions about the pool and the policy, with sources",
     ["tests/test_assistant_mcp.py::test_who_has_run_kubernetes_streams_an_answer_with_cv_sources", "tests/test_assistant_mcp.py::test_policy_questions_cite_the_policy_section"], []),
    ("BR-10", "Follow a recruiter-led interview: live transcript, suggested questions, key points, CV conflicts",
     ["tests/test_copilot_compliance.py::test_strong_interview_transcript_is_labelled_and_key_points_are_ticked",
      "tests/test_copilot_day3.py::test_a_claim_that_conflicts_with_the_cv_shows_both_quotes_and_a_polite_question_and_a_matching_claim_shows_nothing"], ["copilot_eval"]),
    ("BR-11", "Warn at once on a question that must not be asked",
     ["tests/test_copilot_compliance.py::test_a_forbidden_question_is_flagged_at_once_and_its_answer_is_not_scored", "tests/test_copilot_eval.py::test_every_planned_moment_is_caught_and_the_warning_is_fast"], ["copilot_eval"]),
    ("BR-12", "Draft emails; send nothing without a person's approval",
     ["tests/test_emails.py::test_nothing_reaches_outbox_sent_without_a_persons_approval", "tests/test_emails.py::test_approving_writes_an_eml_file_logs_who_approved_and_sets_sent"], []),
    ("BR-13", "Check every score has real evidence and no protected detail was used, before the recruiter sees it",
     ["tests/test_checker.py::test_a_clean_screening_is_checked_and_every_screened_candidate_has_a_status", "tests/test_checker.py::test_the_checker_reports_and_never_changes_a_score"], []),
    ("BR-14", "Ignore instructions hidden in CVs, emails or spoken answers",
     ["tests/test_attacks.py::test_cv_attacks_change_no_score_and_no_stage_and_are_flagged", "tests/test_attacks.py::test_a_spoken_order_to_give_full_marks_and_end_the_interview_is_just_text",
      "tests/test_attacks.py::test_an_email_reply_cannot_move_the_candidate_to_the_next_stage"], ["attack_report"]),
    ("BR-15", "One scorecard per candidate with every score, quote and link to the moment in the recording; the recruiter's decision and reason",
     ["tests/test_day4_scorecard.py::test_every_quote_shown_is_verified_and_the_play_link_carries_the_right_time", "tests/test_day4.py::test_the_recruiter_records_a_decision_with_a_reason_and_it_is_logged"], ["journey"]),
    ("BR-16", "Changing only name, gender or age clues, or the accent of the same answer, does not change the score",
     ["tests/test_identity_swap.py::test_the_pipeline_scores_every_variant_the_same_and_keeps_the_must_haves", "tests/test_accent_test.py::test_one_answer_spoken_two_ways_is_really_transcribed_and_scored"],
     ["identity_swap", "accent_test"]),
    ("BR-17", "Cost per 100 CVs and per interview, and how fast the voice interview responds",
     ["tests/test_cost_speed.py::test_the_numbers_are_per_unit_from_the_logged_calls", "tests/test_cost_speed.py::test_the_trust_page_shows_cost_speed_and_the_latest_reports"], ["cost_and_speed"]),
    ("BR-18", "A governance pack for the EU AI Act: classification, model card, risk register and evidence",
     ["tests/test_governance_pack.py::test_every_control_and_test_the_register_names_really_exists", "tests/test_governance.py::test_the_governance_pack_passes_its_check"], []),
    ("BR-19", "Explain to a candidate, on request, why they were not shortlisted, reviewed by a recruiter before sending",
     ["tests/test_candidate_rights.py::test_the_explanation_is_drafted_from_their_own_evidence_and_waits_for_a_person",
      "tests/test_day4.py::test_a_candidate_not_shortlisted_can_ask_why_and_a_recruiter_reviews_it_first"], []),
    ("BR-20", "Check certifications against a register and flag overlapping job dates",
     ["tests/test_credentials.py::test_a_known_certification_matches_by_name_or_short_name_and_an_unknown_one_is_flagged",
      "tests/test_credentials.py::test_overlapping_jobs_at_different_employers_are_flagged_and_a_normal_handover_is_not"], []),
]

TEXT_SUFFIXES = {".py", ".md", ".html", ".json", ".txt", ".csv", ".yml", ".yaml", ".toml", ".css", ".js", ".cfg", ".ini", ".sh"}
FICTIONAL_DOMAINS = ("example.com", "example.org", "example.net", ".example", "localhost", ".test", ".invalid")  # the reserved names nobody owns
KEY_RX = re.compile(r"sk-or-v1-[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{32,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{20,}|AIza[0-9A-Za-z_-]{30}|"
                    r"(?i:(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"][A-Za-z0-9_\-]{24,}['\"])")
EMAIL_RX = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
LARGE_BYTES = 15 * 1024 * 1024
MODEL_SUFFIXES = {".onnx", ".pt", ".pth", ".bin", ".safetensors", ".gguf", ".ckpt", ".h5"}


def git(*args: str) -> str:
    done = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return done.stdout


def repo_checks() -> list[dict]:
    out = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        out.append({"check": name, "ok": bool(ok), "detail": detail})

    files = [f for f in git("ls-files").splitlines() if f]
    add("no .env file is tracked, now or in the history", not any(Path(f).name == ".env" for f in files) and not git("log", "--all", "--name-only", "--format=", "--", ".env", "**/.env").strip(),
        "git ls-files and git log --all")
    add(".gitignore covers .env, data/, storage/, the raw audio in reports/ and the virtual environment",
        all(git("check-ignore", p).strip() for p in (".env", "data/hiring.db", "storage/interviews/1/x.wav", "reports/accent_audio/x.wav", ".venv/x")), ".env, data/, storage/, reports/accent_audio/, .venv/")
    key_hits = []
    for f in files:
        p = Path(f)
        if p.suffix.lower() in TEXT_SUFFIXES and p.exists() and p.stat().st_size < 2_000_000 and "static/vendor" not in f.replace("\\", "/"):
            for m in KEY_RX.finditer(p.read_text(encoding="utf-8", errors="ignore")):
                if "test-secret" not in m.group(0) and "not-real" not in m.group(0):
                    key_hits.append(f"{f}: {m.group(0)[:12]}...")
    add("no API key or secret in any tracked file", not key_hits, "; ".join(key_hits[:5]) or f"{len(files)} files scanned")
    real = ""
    env = Path(".env")
    if env.exists():
        for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and re.search(r"KEY|TOKEN|SECRET|PASSWORD", line.split("=", 1)[0], re.I):
                real = line.split("=", 1)[1].strip().strip("'\"")
                if len(real) >= 12:
                    hits = git("grep", "-l", "-F", real, *git("rev-list", "--all").split()[:300]).strip() if git("rev-list", "--all").strip() else ""
                    add(f"the real value of {line.split('=')[0]} in .env appears nowhere in the files or history", not hits, "searched every commit" if not hits else hits.splitlines()[0])
    hist = git("log", "--all", "-p", "-G", r"sk-or-v1-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}", "--format=%h", "--", ".").strip()
    add("no API key pattern appears anywhere in the history", not hist, "git log --all -G (key patterns)" if not hist else f"commits: {hist.split()[:3]}")
    emails = {}
    for f in files:
        p = Path(f)
        if p.suffix.lower() in TEXT_SUFFIXES and p.exists() and p.stat().st_size < 2_000_000 and "static/vendor" not in f.replace("\\", "/") and not f.startswith(("starter_kit/question_bank", "reports/final_check")):  # the report quotes what it found
            for m in EMAIL_RX.finditer(p.read_text(encoding="utf-8", errors="ignore")):
                dom = m.group(1).lower()
                if not dom.endswith(FICTIONAL_DOMAINS):
                    emails.setdefault(m.group(0), f)
    add("no real personal data: every e-mail address in the files is a fictional one (example.com and similar)", not emails, "; ".join(f"{e} ({f})" for e, f in list(emails.items())[:6]) or "all addresses are fictional")
    big = [f"{f} ({Path(f).stat().st_size // 1_000_000} MB)" for f in files if Path(f).exists() and (Path(f).stat().st_size > LARGE_BYTES or Path(f).suffix.lower() in MODEL_SUFFIXES)]
    add("no large files or model weights are tracked", not big, "; ".join(big[:5]) or "largest tracked file is under 15 MB; no model weights")
    add("fictional data only is stated in the project rules", "Fictional data only" in Path("CLAUDE.md").read_text(encoding="utf-8"), "CLAUDE.md rule 11")
    dirty = "\n".join(l for l in git("status", "--porcelain").splitlines() if not l[3:].startswith(("reports/", "evidence/", "governance/")))  # these are written by the scripts themselves
    add("the working tree is committed (nothing left uncommitted)", not dirty, "clean" if not dirty else f"{len(dirty.splitlines())} changed file(s)")
    return out


def defined(path: Path) -> set[str]:
    return {n.name for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def requirement_checks(run: dict) -> list[dict]:
    from scripts.governance_pack import test_status

    rows = []
    for rid, what, tests, reports in REQUIREMENTS:
        problems, statuses = [], []
        for t in tests:
            f, _, name = t.partition("::")
            if not Path(f).exists() or name not in defined(Path(f)):
                problems.append(f"missing test {t}")
                continue
            s = test_status(run, t)
            statuses.append(s)
            if s != "PASS":
                problems.append(f"{name}: {s}")
        for r in reports:
            doc = load_report(r)
            if doc is None:
                problems.append(f"report {r} is missing")
            else:
                from evals.common import age_days

                if age_days(doc) > MAX_AGE_DAYS:
                    problems.append(f"report {r} is older than {MAX_AGE_DAYS} days")
                elif not doc["passed"]:
                    problems.append(f"report {r} did not pass")
        rows.append({"id": rid, "requirement": what, "status": "OK" if not problems else "MISSING", "tests": len(tests), "reports": reports, "problems": problems})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()
    if args.full:
        print("Running the journey in fake mode ...")
        subprocess.run([sys.executable, "-m", "scripts.journey", "--fake"], check=False)
    ids = None if args.full else sorted({t for _, _, tests, _ in REQUIREMENTS for t in tests})
    run = run_tests(ids)
    repo, reqs = repo_checks(), requirement_checks(run)
    print("\nREPOSITORY")
    for r in repo:
        print(f"  {'OK     ' if r['ok'] else 'MISSING'} {r['check']}" + (f"  ({r['detail']})" if r["detail"] and not r["ok"] else ""))
    print(f"\nREQUIREMENTS (tests: {run['summary']})")
    for r in reqs:
        print(f"  {r['status']:<8}{r['id']}  {r['requirement']}" + (f"\n          {'; '.join(r['problems'])}" if r["problems"] else ""))
    ok_n = sum(r["status"] == "OK" for r in reqs)
    all_ok = all(r["ok"] for r in repo) and ok_n == len(reqs)
    md = ["## Repository", table(["check", "result", "detail"], [[r["check"], "OK" if r["ok"] else "MISSING", r["detail"]] for r in repo]), "",
          f"## Requirements BR-01 to BR-20: {ok_n} of {len(reqs)} OK", f"Tests run for this check: {run['summary']} ({'the whole suite' if run['full'] else 'the tests each requirement names'}).", "",
          table(["id", "requirement", "status", "tests", "reports", "problems"], [[r["id"], r["requirement"], r["status"], r["tests"], ", ".join(r["reports"]) or "-", "; ".join(r["problems"]) or "-"] for r in reqs]), "",
          "## How to read this", "OK means every test the requirement names exists and passed in this run, and every report it names is fresh and passed. MISSING goes into the demo as a known gap. "
          "Fake models were used where the reports say so.", ""]
    write_report("final_check", "Final check: the repository and requirements BR-01 to BR-20", {"full_suite": run["full"]},
                 {"repository": repo, "requirements": reqs, "tests": run["summary"], "failing_tests": sorted(k for k, v in run["results"].items() if v == "FAIL"), "ok": ok_n, "of": len(reqs)}, all_ok, "\n".join(md))
    print(f"\nFinal check: {ok_n} of {len(reqs)} requirements OK; repository {'clean' if all(r['ok'] for r in repo) else 'has problems'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
