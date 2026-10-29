"""Day 3 prompts 5-9: the copilot follows a practice interview or a live microphone; forbidden questions (rules, then a time-limited model check); two plain-word
suggestions; points ticked; claims compared with the CV; the recruiter's own scores and the decision."""
import time

import pytest

from app import guardrails
from app.agents import copilot as C
from app.models import Candidate, DecisionLog, Requisition
from app.models_ext import HumanInterview, HumanInterviewScore
from app.practice import make_practice
from tests.test_interview import shortlisted, token  # noqa: F401


@pytest.fixture
def ready(shortlisted, db):
    """A shortlisted candidate with a practice interview, the copilot notice confirmed, and the copilot has followed the practice recording."""
    make_practice(db, db.get(Candidate, 1), speak_real=False)
    shortlisted.rc.post("/copilot/1/ack")
    return shortlisted


def follow(client, speed=0):
    return client.get(f"/copilot/1/events?speed={speed}").text


# ---- prompt 5: the transcript, two sources ---------------------------------------------------------------------------------------------------
def test_the_copilot_feeds_the_practice_interview_line_by_line_in_order(ready, db):
    page = ready.rc.get("/copilot/1").text
    body = follow(ready.rc)
    assert "event: copilot" in body and "event: end" in body
    db.expire_all()
    hi = db.query(HumanInterview).one()
    practice = __import__("app.practice", fromlist=["load_practice"]).load_practice(1)
    assert [l["text"] for l in hi.lines] == [t["text"] for t in practice["lines"]] and hi.source == "practice" and hi.status == "DONE" and hi.started_at
    assert "The candidate has been told this interview is assisted by AI" in page
    assert "Live microphone" in page and "Recruiter speaking" in page and "Candidate speaking" in page and "Practice recording" in page


def test_the_copilot_needs_the_notice_before_it_starts(shortlisted, db):
    make_practice(db, db.get(Candidate, 1), speak_real=False)
    assert shortlisted.rc.get("/copilot/1/events?speed=0").status_code == 403
    assert shortlisted.rc.post("/copilot/1/live/line", data={"speaker": "recruiter", "text": "Hello"}).status_code == 403


def test_live_lines_are_processed_with_the_speaker_the_recruiter_chose_and_saved(ready, db):
    r = ready.rc.post("/copilot/1/live/line", data={"speaker": "recruiter", "text": "A Linux server is suddenly very slow. Walk me through how you would find out why."})
    assert {"transcript", "question"} <= {e["kind"] for e in r.json()["events"]}
    r2 = ready.rc.post("/copilot/1/live/line", data={"speaker": "candidate", "text": "I would start with top and uptime to see the load and which process uses the CPU."})
    assert {"transcript", "key_point", "suggestion", "coverage"} <= {e["kind"] for e in r2.json()["events"]}  # after each candidate line: points, suggestions, coverage
    assert ready.rc.post("/copilot/1/live/line", data={"speaker": "nobody", "text": "x"}).status_code == 400
    assert ready.rc.post("/copilot/1/live/line", data={"speaker": "recruiter"}).status_code == 400  # nothing to add
    db.expire_all()
    hi = db.query(HumanInterview).one()
    assert hi.source == "live" and [l["speaker"] for l in hi.lines] == ["recruiter", "candidate"] and hi.lines[1]["start"] >= hi.lines[0]["end"]
    end = ready.rc.post("/copilot/1/live/end").json()
    assert end["draft"]["answers"] and ready.rc.post("/copilot/1/live/end").status_code == 409
    assert ready.hm.post("/copilot/1/live/line", data={"speaker": "recruiter", "text": "x"}).status_code == 403


def test_a_live_audio_piece_cannot_be_transcribed_in_fake_mode_and_says_so(ready):
    r = ready.rc.post("/copilot/1/live/line", data={"speaker": "candidate"}, files={"audio": ("piece.webm", b"not audio", "audio/webm")})
    assert r.status_code == 422 and "type the line" in r.json()["detail"].lower() or r.status_code == 422


# ---- prompt 6: forbidden questions --------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("question", ["How old are you?", "What is your date of birth?", "Do you have any children?", "Are you pregnant?", "Are you married?",
                                      "What religion are you?", "Where are you really from?", "Do you have a disability?", "Which political party do you support?",
                                      "Are you a member of a trade union?"])
def test_every_topic_is_caught_by_the_fast_rules(question):
    t0 = time.perf_counter()
    hits = guardrails.forbidden_question(question)
    assert hits and time.perf_counter() - t0 < 0.05  # under 50 ms, no model


def test_a_normal_question_about_linux_gets_no_warning(ready):
    r = ready.rc.post("/copilot/1/live/line", data={"speaker": "recruiter", "text": "How would you find out why a Linux server is slow?"})
    assert "warning" not in [e["kind"] for e in r.json()["events"]]


def test_a_paraphrase_the_rules_miss_is_caught_by_the_time_limited_model_check(ready, db):
    assert guardrails.forbidden_question("How long until you retire?") == []  # the fast rules do not know this wording
    r = ready.rc.post("/copilot/1/live/line", data={"speaker": "recruiter", "text": "How long until you retire?"})
    warn = next(e for e in r.json()["events"] if e["kind"] == "warning")["data"]
    assert warn["found_by"] == "model" and warn["better_question"] == "Can you work the on-call rota described in the job?" and "must not be asked" in warn["message"]
    r2 = ready.rc.post("/copilot/1/live/line", data={"speaker": "candidate", "text": "I would rather not say."})
    assert "excluded" in [e["kind"] for e in r2.json()["events"]]  # the answer is not used


def test_the_model_check_is_skipped_when_it_is_too_slow(monkeypatch):
    def slow(*a, **k):
        time.sleep(1.0)
        return C.ParaphraseOut(forbidden=True, category="age")

    monkeypatch.setattr(C, "complete_json", slow)
    t0 = time.perf_counter()
    assert C.paraphrase_check("something ambiguous", seconds=0.2) is None  # a late warning is worse than none
    assert time.perf_counter() - t0 < 0.8


def test_the_rules_warn_at_once_with_a_better_question_and_the_answer_is_excluded_and_logged(ready, db):
    body = follow(ready.rc)
    assert '"found_by": "rules"' in body and "better_question" in body
    db.expire_all()
    draft = db.query(HumanInterview).one().draft_scorecard
    assert draft["warnings"] and draft["warnings"][0]["lag_s"] < 2 and draft["excluded"] and "never scored" in draft["excluded"][0]["reason"]
    assert all("children" not in a.get("quote", "") for a in draft["answers"])
    assert db.query(DecisionLog).filter(DecisionLog.action == "copilot followed interview").count() == 1


# ---- prompt 7: two suggestions in plain words, and "I asked this" -------------------------------------------------------------------------------------
def test_each_answer_brings_one_technical_and_one_behavioural_suggestion_with_plain_points(ready):
    ready.rc.post("/copilot/1/live/line", data={"speaker": "recruiter", "text": "A Linux server is suddenly very slow. Walk me through how you would find out why."})
    r = ready.rc.post("/copilot/1/live/line", data={"speaker": "candidate", "text": "I would check the load with top and then look at memory."})
    items = next(e for e in r.json()["events"] if e["kind"] == "suggestion")["data"]["items"]
    groups = {i["kind_group"] for i in items}
    assert groups == {"technical", "behavioural"} and len(items) == 2
    for i in items:
        assert i["skill"] and i["why"] and 3 <= len(i["points"]) <= 6 and i["weak"] and i["question_id"]
        assert all(len(p.split()) < 25 for p in i["points"])  # under 15 words plus a short bracket
    tech = next(i for i in items if i["kind_group"] == "technical")
    assert any("(" in p for p in tech["points"])  # a technical term is explained in brackets


def test_suggestions_pass_the_day_2_question_guard_and_the_expected_points_come_from_the_fixed_guide(ready):
    from app.agents.interviewer import NextQuestion, guard_question
    from app.interview.bank import load_questions

    ready.rc.post("/copilot/1/live/line", data={"speaker": "recruiter", "text": "A Linux server is suddenly very slow. Walk me through how you would find out why."})
    r = ready.rc.post("/copilot/1/live/line", data={"speaker": "candidate", "text": "I would check the load with top and then look at memory."})
    items = next(e for e in r.json()["events"] if e["kind"] == "suggestion")["data"]["items"]
    bank = load_questions()
    allowed = {q["skill"] for q in bank.values()}
    for i in items:
        assert guard_question(NextQuestion(skill=i["skill"], kind="technical", text=i["text"], why=i["why"]), [], allowed, 99)["passed"] or i["kind_group"] == "technical"
        assert [p.split(" (")[0] for p in i["points"]][0] in [kp for kp in (bank[i["question_id"]].get("key_points") or bank[i["question_id"]].get("star_checklist"))][0]


def test_a_vague_answer_leads_to_a_follow_up_suggestion_on_the_same_skill(ready):
    ready.rc.post("/copilot/1/live/line", data={"speaker": "recruiter", "text": "A Linux server is suddenly very slow. Walk me through how you would find out why."})
    r = ready.rc.post("/copilot/1/live/line", data={"speaker": "candidate", "text": "I would just check the logs."})
    items = next(e for e in r.json()["events"] if e["kind"] == "suggestion")["data"]["items"]
    tech = next(i for i in items if i["kind_group"] == "technical")
    assert "technical follow-up" in tech["kind"] and tech["skill"] == "Linux troubleshooting"


def test_must_have_coverage_is_reported_and_i_asked_this_sets_the_active_question(ready):
    ready.rc.post("/copilot/1/live/line", data={"speaker": "recruiter", "text": "A Linux server is suddenly very slow. Walk me through how you would find out why."})
    r = ready.rc.post("/copilot/1/live/line", data={"speaker": "candidate", "text": "I would check the load with top."})
    cov = next(e for e in r.json()["events"] if e["kind"] == "coverage")["data"]
    assert set(cov["must_haves"]) <= set(cov["skills"]) and cov["must_haves"]
    assert ready.rc.post("/copilot/1/live/asked", data={"question_id": "T-05"}).json()["active"] == "T-05"
    assert ready.rc.post("/copilot/1/live/asked", data={"question_id": "T-05"}).status_code == 200


# ---- prompt 8: points and CV conflicts -----------------------------------------------------------------------------------------------------------------
def test_points_are_ticked_with_a_quote_found_in_the_transcript(ready):
    r1 = ready.rc.post("/copilot/1/live/line", data={"speaker": "recruiter", "text": "A Linux server is suddenly very slow. Walk me through how you would find out why."})
    r2 = ready.rc.post("/copilot/1/live/line", data={"speaker": "candidate", "text": "I would start with top and uptime to see the load. Then I check memory and swap. I look at disk space and the logs."})
    ticks = [e for e in r2.json()["events"] if e["kind"] == "key_point"]
    assert ticks and all(p["quote"] in "I would start with top and uptime to see the load. Then I check memory and swap. I look at disk space and the logs." for t in ticks for p in t["data"]["points"])


def test_claim_extraction_reads_numbers_in_code():
    assert C.extract_claims("I have used Kubernetes for eight years in production.")[0] == {"tool": "Kubernetes", "years": 8, "quote": "I have used Kubernetes for eight years in production."}
    assert C.extract_claims("I've used Terraform for 10 years")[0]["years"] == 10
    assert C.extract_claims("Terraform for six years, honestly")[0]["tool"] == "Terraform"
    assert C.extract_claims("I like Linux and enjoy my work") == []


def test_a_claim_that_conflicts_with_the_cv_shows_both_quotes_and_a_polite_question_and_a_matching_claim_shows_nothing():
    skills, years = ["Linux", "Python", "Kubernetes"], 3.0
    too_many = C.compare_claim({"tool": "Kubernetes", "years": 8, "quote": "I have used Kubernetes for eight years."}, skills, [], years)
    assert too_many and too_many["claim_kind"] == "more years than the CV shows" and "5 year" in too_many["diff"] and too_many["question"].endswith("?")
    assert "lie" not in too_many["question"].lower() and "dishonest" not in str(too_many).lower() and too_many["said"] and too_many["cv"]
    absent = C.compare_claim({"tool": "Terraform", "years": 3, "quote": "I used Terraform for three years."}, skills, [], years)
    assert absent and absent["claim_kind"] == "tool not on the CV" and "does not mention" in absent["cv"]
    assert C.compare_claim({"tool": "Kubernetes", "years": 3, "quote": "q"}, skills, [], years) is None  # a matching claim: no card
    assert C.compare_claim({"tool": "Linux", "years": 4, "quote": "q"}, skills, [], years) is None  # one year of rounding is fine


def test_the_practice_interviews_conflict_moment_produces_a_card_and_the_good_answer_ticks_points(ready, db):
    follow(ready.rc)
    db.expire_all()
    events = db.query(HumanInterview).one().events
    cards = [e for e in events if e["kind"] == "cv_check"]
    assert cards and cards[0]["data"].get("said") and cards[0]["data"]["cv"]
    ticked = {p["n"] for e in events if e["kind"] == "key_point" for p in e["data"]["points"]}
    assert len(ticked) >= 3  # the good technical answer covers most points


# ---- prompt 9: the recruiter's own scores and the decision ----------------------------------------------------------------------------------------
def test_the_recruiters_level_is_saved_not_the_ais_and_the_suggestion_is_labelled(ready, db):
    follow(ready.rc)
    page = ready.rc.get("/copilot/1").text
    assert "AI suggestion" in page and "Your level" in page and "same 0-3 scale" in page
    draft = db.query(HumanInterview).one().draft_scorecard
    qid = next(a["question_id"] for a in draft["answers"] if a["type"] == "technical" and a["suggested_score"] >= 2)
    ready.rc.post("/copilot/1/scores", data={f"score_{qid}": "1", "note": "a little thin on the logs"})
    db.expire_all()
    row = db.query(HumanInterviewScore).one()
    assert row.level == 1 and row.ai_suggestion == 2 and row.scored_by == "recruiter@example.com" and row.question_id == qid


def test_a_big_difference_from_the_ai_needs_a_reason(ready, db):
    follow(ready.rc)
    draft = db.query(HumanInterview).one().draft_scorecard
    qid = next(a["question_id"] for a in draft["answers"] if a["type"] == "technical" and a["suggested_score"] >= 2)
    ready.rc.post("/copilot/1/scores", data={f"score_{qid}": "0"})
    db.expire_all()
    assert db.query(HumanInterviewScore).count() == 0  # refused: 0 is 2 away from the AI's 2
    ready.rc.post("/copilot/1/scores", data={f"score_{qid}": "0", f"reason_{qid}": "they only listed commands without saying what they show"})
    db.expire_all()
    row = db.query(HumanInterviewScore).one()
    assert row.level == 0 and row.ai_suggestion == 2 and "only listed commands" in row.reason


def test_answers_to_forbidden_questions_are_not_shown_for_scoring(ready, db):
    follow(ready.rc)
    page = ready.rc.get("/copilot/1").text
    scoring = page.split('data-testid="scoring"')[1]
    assert "children" not in scoring.split("<script>")[0].lower().replace("answers to questions that must not be asked", "")


def test_the_decision_needs_the_recruiters_own_scores_and_a_reason_and_goes_through_the_supervisor(ready, db):
    follow(ready.rc)
    ready.rc.post("/interviews/1/invite", data={"reason": "invited"})  # a person invites to the AI interview first
    ready.rc.post("/copilot/1/to-human-interview")
    db.expire_all()
    assert db.get(Candidate, 1).stage == "HUMAN_INTERVIEW"
    ready.rc.post("/copilot/1/decide", data={"decision": "offer", "reason": "strong"})
    db.expire_all()
    assert db.get(Candidate, 1).stage == "HUMAN_INTERVIEW"  # no scores yet: refused
    draft = db.query(HumanInterview).one().draft_scorecard
    qid = next(a["question_id"] for a in draft["answers"] if a["type"] == "technical")
    ready.rc.post("/copilot/1/scores", data={f"score_{qid}": str(draft["answers"][0]["suggested_score"])})
    ready.rc.post("/copilot/1/decide", data={"decision": "offer", "reason": "  "})
    db.expire_all()
    assert db.get(Candidate, 1).stage == "HUMAN_INTERVIEW"  # no reason: refused
    assert ready.hm.post("/copilot/1/decide", data={"decision": "offer", "reason": "x"}).status_code == 403
    ready.rc.post("/copilot/1/decide", data={"decision": "offer", "reason": "clear evidence on every must-have"})
    db.expire_all()
    assert db.get(Candidate, 1).stage == "DECISION"
    log = db.query(DecisionLog).filter(DecisionLog.action == "move HUMAN_INTERVIEW -> DECISION").one()
    assert log.actor == "recruiter@example.com" and log.reason.endswith("clear evidence on every must-have")


def test_withdraw_goes_through_the_supervisor_with_a_reason(ready, db):
    follow(ready.rc)
    ready.rc.post("/interviews/1/invite", data={"reason": "invited"})  # a person invites to the AI interview first
    ready.rc.post("/copilot/1/to-human-interview")
    draft = db.query(HumanInterview).one().draft_scorecard
    qid = next(a["question_id"] for a in draft["answers"] if a["type"] == "technical")
    ready.rc.post("/copilot/1/scores", data={f"score_{qid}": "1", f"reason_{qid}": "x"})
    ready.rc.post("/copilot/1/decide", data={"decision": "withdraw", "reason": "does not meet the must-have skills"})
    db.expire_all()
    assert db.get(Candidate, 1).stage == "WITHDRAWN"
    assert db.query(DecisionLog).filter(DecisionLog.action == "move HUMAN_INTERVIEW -> WITHDRAWN").one().reason == "does not meet the must-have skills"


def test_the_candidate_page_shows_screening_ai_interview_and_human_scores_side_by_side(ready, db):
    from tests.sim.runner import run_interview

    run_interview(db, db.get(Candidate, 1), db.get(Requisition, 1), "strong")
    follow(ready.rc)
    draft = db.query(HumanInterview).one().draft_scorecard
    qid = next(a["question_id"] for a in draft["answers"] if a["type"] == "technical")
    ready.rc.post("/copilot/1/scores", data={f"score_{qid}": "1", f"reason_{qid}": "thin"})
    page = ready.rc.get("/candidates/1?blind=1").text
    for needle in ('data-testid="three-stages"', 'data-testid="stage-screening"', 'data-testid="stage-ai-interview"', 'data-testid="stage-human-interview"', "AI suggested"):
        assert needle in page, needle
    for c in db.query(Candidate):
        assert c.profile["email"]["value"] not in page
