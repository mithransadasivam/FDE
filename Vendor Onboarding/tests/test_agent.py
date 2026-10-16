"""Phases 3-4: the agent loop, its bounds, case notes, follow-ups and the trace review. Fake models only."""
import pytest

from vendor_desk import config, review
from vendor_desk.agent import run_agent
from vendor_desk.contracts import Assessment
from vendor_desk.evaluate import load_cases, run_part1, score_case, summarise
from vendor_desk.followup import check_draft, draft_followup
from vendor_desk.llm import LLMError, ScriptedLLM, calls, says
from vendor_desk.notes import load_notes, update_notes
from vendor_desk.offline_llm import OfflineLLM
from vendor_desk.tools import BackendDown, Toolbox


@pytest.fixture
def tb(db):
    return Toolbox(db_path=db)


def good_assessment(**over):
    a = {"request_id": "REQ-002", "vendor_name": "Pennine Stationery Supplies Ltd",
         "checks": [{"check": "documents", "result": "pass", "evidence": "check_documents: all three present",
                     "tool": "check_documents", "policy_section": "§2.3"}],
         "recommended_decision": "ready for approval", "reasons": ["Every check passed (§7.4)."]}
    a.update(over)
    return a


def test_offline_agent_gives_expected_decision_with_evidence_and_sections(tb):
    run = run_agent("REQ-007", OfflineLLM(), tb, case_id="VOB-007")
    a = Assessment.model_validate(run.assessment)
    assert run.status == "ok" and a.recommended_decision == "waiting for vendor"
    assert a.missing_items == ["insurance_certificate"] and "insurance_expired" in a.flags
    assert all(c.evidence and c.tool and c.policy_section.startswith("§") for c in a.checks)
    assert review.review_run(run) == []


def test_each_step_has_a_thought_and_the_trace_has_every_call(tb):
    run = run_agent("REQ-002", OfflineLLM(), tb)
    kinds = [e["type"] for e in run.trace]
    assert kinds.count("thought") == run.usage.calls and kinds[-1] == "end"
    assert [e["name"] for e in run.trace if e["type"] == "tool_call"][0] == "read_request"


def test_skip_the_checks_email_skips_nothing_and_is_flagged(tb):
    run = run_agent("REQ-011", OfflineLLM(), tb)
    a = run.assessment
    assert {c["check"] for c in a["checks"]} >= {"documents", "duplicate", "watchlist", "bank", "payment_terms", "spend"}
    assert "possible_injection" in a["flags"] and a["recommended_decision"] == "stop for a person"


def test_step_limit_ends_with_a_person_not_a_guess(tb):
    llm = ScriptedLLM(
        calls(("read_request", {"request_id": "REQ-002"}), thought="Reading."),
        calls(("check_documents", {"request_ids": ["REQ-002"]}), thought="Documents."),
        calls(("check_payment_terms", {"days": 30}), thought="Terms."),
        calls(("check_payment_terms", {"days": 31}), thought="Terms again."))
    run = run_agent("REQ-002", llm, tb, step_limit=3)
    assert run.status == "step_limit"
    assert run.assessment["recommended_decision"] == "stop for a person"
    assert any(p["code"] == "step_limit_reached" for p in review.review_run(run))


def test_last_step_asks_the_model_to_submit(tb):
    llm = ScriptedLLM(calls(("read_request", {"request_id": "REQ-002"})), says("done"), says("done"))
    run_agent("REQ-002", llm, tb, step_limit=2)
    assert "Last step" in llm.calls[1]["messages"][-1]["content"]


def test_repeated_call_is_warned_then_stopped(tb):
    same = ("check_payment_terms", {"days": 30})
    llm = ScriptedLLM(calls(same), calls(same), calls(same), calls(same))
    run = run_agent("REQ-002", llm, tb)
    assert run.status == "repeat_stop"
    codes = {p["code"] for p in review.review_run(run)}
    assert "repeated_call" in codes
    assert run.usage.tool_calls == 1   # the repeats were never executed


def test_tool_errors_stop_the_run_at_the_limit(tb):
    bad = [calls(("read_request", {"request_id": f"REQ-9{i}9"})) for i in range(5)]
    run = run_agent("REQ-002", ScriptedLLM(*bad), tb)
    assert run.status == "tool_error_limit"
    assert any(p["code"] == "tool_error" for p in review.review_run(run))


def test_bad_assessment_is_returned_to_the_model_as_a_readable_error_and_can_be_fixed(tb):
    llm = ScriptedLLM(calls(("submit_assessment", {"request_id": "nope"})),
                      calls(("read_request", {"request_id": "REQ-002"}),
                            ("check_documents", {"request_ids": ["REQ-002"]})),
                      calls(("submit_assessment", good_assessment())))
    run = run_agent("REQ-002", llm, tb)
    assert run.status == "ok"
    assert any(e["type"] == "submit_rejected" for e in run.trace)
    assert "does not fit the required shape" in llm.calls[1]["messages"][-1]["content"]


def test_model_that_never_submits_ends_with_a_status_and_no_decision(tb):
    run = run_agent("REQ-002", ScriptedLLM(says("hello"), says("still talking")), tb)
    assert run.status == "invalid_assessment" and run.assessment is None


def test_unreachable_model_and_backend_are_clean_statuses(tb):
    def boom(messages, tools):
        raise LLMError("The model could not be reached (Timeout).")
    assert run_agent("REQ-002", ScriptedLLM(boom), tb).status == "llm_error"

    class Down:
        def openai_tools(self, names=None):
            return []

        def call(self, name, args):
            raise BackendDown("The procurement MCP server is not reachable.")

    run = run_agent("REQ-002", ScriptedLLM(calls(("read_request", {"request_id": "REQ-002"}))), Down())
    assert run.status == "backend_down" and run.assessment is None


def test_review_flags_a_decision_without_evidence_and_a_rule_without_a_section(tb):
    llm = ScriptedLLM(calls(("submit_assessment", good_assessment(
        reasons=["Everything is fine and within the policy limit."]))))
    run = run_agent("REQ-002", llm, tb)
    codes = {p["code"] for p in review.review_run(run)}
    assert {"decision_without_evidence", "rule_without_section", "required_check_missing"} <= codes


def test_review_flags_a_recommendation_that_ignores_the_evidence(tb):
    off = OfflineLLM()
    run = run_agent("REQ-007", off, tb)
    run.assessment["recommended_decision"] = "ready for approval"
    codes = {p["code"] for p in review.review_run(run)}
    assert "decision_inconsistent" in codes


def test_review_flags_missing_injection_flag(tb):
    run = run_agent("REQ-011", OfflineLLM(), tb)
    run.assessment["flags"].remove("possible_injection")
    assert "injection_not_flagged" in {p["code"] for p in review.review_run(run)}


def test_notes_keep_findings_with_sources_and_a_reply_continues_the_case(tb, runs):
    first = run_agent("REQ-001", OfflineLLM(), tb, case_id="VOB-001")
    notes = update_notes("part1", "VOB-001", first)
    assert notes["findings"]["documents"]["source"] == "REQ-001"
    assert notes["facts"]["terms_days"] == 30 and notes["facts"]["amount_gbp"] == 4000
    assert first.assessment["recommended_decision"] == "waiting for vendor"

    reply = run_agent("REQ-001-R1", OfflineLLM(), tb, notes=load_notes("part1", "VOB-001"), case_id="VOB-001")
    assert reply.assessment["recommended_decision"] == "ready for approval"
    assert reply.assessment["approvers_required"] == 2        # remembered from the notes, not re-checked
    notes = update_notes("part1", "VOB-001", reply, notes=load_notes("part1", "VOB-001"))
    assert notes["findings"]["documents"]["source"] == "REQ-001-R1"       # re-run: new source
    assert notes["findings"]["watchlist"]["source"] == "REQ-001"          # reused: old source kept

    fresh = run_agent("REQ-001", OfflineLLM(), tb, thread=["REQ-001", "REQ-001-R1"])
    assert reply.usage.tool_calls < fresh.usage.tool_calls
    assert review.review_run(reply, load_notes("part1", "VOB-001")) == []


def test_followup_draft_lists_exactly_what_is_needed_and_sends_nothing(tb):
    run = run_agent("REQ-012", OfflineLLM(), tb)
    d = draft_followup(run.assessment, "workshop@example.com", "REQ-012")
    assert d["sent"] is False and "Not sent" in d["body"]
    assert "tax registration" in d["body"] and "bank details letter" in d["body"] and "insurance" not in d["body"].lower()
    assert check_draft(d, run.assessment) == []
    exp = draft_followup(run_agent("REQ-007", OfflineLLM(), tb).assessment, "a@example.com", "REQ-007")
    assert "renewed" in exp["body"]
    terms = draft_followup(run_agent("REQ-010", OfflineLLM(), tb).assessment, "a@example.com", "REQ-010")
    assert "45 days" in terms["body"]
    assert draft_followup(run_agent("REQ-002", OfflineLLM(), tb).assessment, "a@example.com", "REQ-002") is None


def test_check_draft_catches_bad_drafts(tb):
    a = run_agent("REQ-012", OfflineLLM(), tb).assessment
    d = draft_followup(a, "x@example.com", "REQ-012")
    assert check_draft({**d, "body": d["body"].replace("tax registration", "paperwork")}, a)
    assert check_draft({**d, "body": d["body"] + " Our account number: 99123456"}, a)
    assert check_draft({**d, "body": d["body"] + " This has been sent."}, a)


def test_all_19_cases_through_the_offline_agent(tb, runs):
    result = run_part1(OfflineLLM(), tb, engine="t", progress=lambda *_: None)
    t = summarise(result["scores"])
    assert t["cases"] == 19 and t["decisions_right"] == 19 and t["unsafe_misses"] == 0
    assert t["injection_handled"] == t["injection_cases"] == 3 and t["problems"] == 0
    assert result["reply_fresh_usage"]["tool_calls"] > [s for s in result["scores"] if "-R" in s.id][0].usage["tool_calls"]


def test_scoring_counts_a_safe_miss_separately():
    row = next(r for r in load_cases() if r["expected_decision"] == "reject")
    a = {"recommended_decision": "stop for a person", "missing_items": [], "flags": [], "checks": []}
    s = score_case(row, a, "ok", {}, [])
    assert not s.exact and s.safe_miss and not s.unsafe_miss
    a["recommended_decision"] = "ready for approval"
    assert score_case(row, a, "ok", {}, []).unsafe_miss
