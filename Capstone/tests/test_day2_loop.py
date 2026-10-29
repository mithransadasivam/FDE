"""Day 2 prompt 11: scoring, and the next-step rule that code (not the model) applies after every answer."""
import pytest

from app.agents.interviewer import MAX_PER_SKILL, InterviewerAgent, Target, get_or_create_session, next_target
from app.db import OpsSession
from app.interview.bank import load_questions
from app.models import Candidate, Requisition
from app.models_ext import InterviewSession, ModelCall
from app.privacy import identity_strings
from tests.test_interview import invited, shortlisted, token  # noqa: F401

PLAN = [{"question_id": f"Q{i}", "skill": s, "core": True, "diagram": None, "reason": ""}
        for i, s in enumerate(["Linux", "Cloud networking", "Incident handling", "Terraform", "Kubernetes", "SQL"])]
MUST = {"Linux", "Cloud networking", "Incident handling"}


def last(**kw):
    base = {"skill": "Linux", "score": 3, "max_score": 3, "has_follow_up": True, "followed_up": False, "deeper_done": False}
    return {**base, **kw}


# ---- the rule itself (pure code, no model) --------------------------------------------------------------------------------------------------
def test_a_weak_answer_is_followed_up_once_on_the_same_skill():
    t = next_target(PLAN, [0], {"Linux": 1}, MUST, 20, last(score=1))
    assert t.action == "follow_up" and t.skill == "Linux"
    assert next_target(PLAN, [0], {"Linux": 2}, MUST, 20, last(score=1, followed_up=True)).action == "new"  # never twice
    assert next_target(PLAN, [0], {"Linux": 1}, MUST, 20, last(score=1, has_follow_up=False)).action == "new"


def test_a_strong_answer_gets_one_deeper_question_when_there_is_time():
    assert next_target(PLAN, [0], {"Linux": 1}, MUST, 20, last()).action == "deeper"
    assert next_target(PLAN, [0], {"Linux": 1}, MUST, 3, last()).action == "new"  # not enough time to go deeper
    assert next_target(PLAN, [0], {"Linux": 2}, MUST, 20, last(deeper_done=True)).action == "new"  # only one deeper question
    assert next_target(PLAN, [0], {"Linux": MAX_PER_SKILL}, MUST, 20, last()).action == "new"  # never more than 3 about one skill


def test_the_next_skill_follows_the_plan_and_never_asks_more_than_three_about_a_skill():
    t = next_target(PLAN, [0, 1], {"Linux": 1, "Cloud networking": 1}, MUST, 20, last(score=2, skill="Cloud networking", followed_up=True))
    assert t == Target("new", idx=2, skill="Incident handling", reason="the next skill in the plan")
    capped = next_target(PLAN, [0], {"Cloud networking": 3, "Incident handling": 0}, MUST, 20, None)
    assert capped.idx == 2  # Cloud networking already had 3 questions: skipped


def test_a_must_have_not_yet_asked_comes_first_when_time_is_short_and_before_the_end():
    order = [0, 2, 3]  # Cloud networking (a must-have) was not asked yet
    t = next_target(PLAN, order, {}, MUST, 6, last(score=3, skill="Terraform", deeper_done=True))
    assert t.action == "new" and t.skill == "Cloud networking"
    t = next_target(PLAN, order, {}, MUST, 0, last(score=3, skill="Terraform", deeper_done=True))
    assert t.action == "new" and t.skill == "Cloud networking"  # even when the time is up
    done = next_target(PLAN, [0, 1, 2], {}, MUST, 0, last(score=3, skill="Incident handling", deeper_done=True))
    assert done.action == "end" and done.reason == "25 minute limit reached"
    assert next_target(PLAN, [0, 1, 2], {}, MUST, 2, None).action == "end"  # fewer than 3 minutes left and every must-have covered
    assert next_target(PLAN, [0, 1, 2, 3, 4, 5], {}, MUST, 20, None) == Target("end", reason="all questions asked")


# ---- the rule inside a real interview ---------------------------------------------------------------------------------------------------------
@pytest.fixture
def agent(invited, db):
    s = get_or_create_session(db, db.get(Candidate, 1))
    s.notice_ack = True
    db.commit()
    a = InterviewerAgent(db, s)
    a.start(db.get(Requisition, 1))
    return a


def strong_answer(agent):
    q = load_questions()[agent.session.state["turns"][-1]["question_id"]]
    return " ".join(d["say"] for d in q["key_point_detail"])


def test_a_strong_answer_gets_one_deeper_question_then_the_interview_moves_on(agent):
    first = agent.session.state["turns"][-1]["question_id"]
    res = agent.submit(text=strong_answer(agent), duration_s=20)
    assert res["score"]["score"] == 3
    assert res["next"]["question_id"] == first and not res["next"]["is_follow_up"] and "could fail" in res["next"]["text"]
    turn = agent.session.state["turns"][-1]
    assert turn["meta"][-1]["why"].startswith("the answer was strong") and turn["meta"][-1]["guard"]["passed"]
    res2 = agent.submit(text=strong_answer(agent), duration_s=20)  # answering the deeper question: scored with the first answer, then on to the next skill
    assert res2["next"]["question_id"] != first and res2["next"]["number"] == 2


def test_a_weak_answer_gets_one_follow_up_and_then_the_next_skill(agent):
    first = agent.session.state["turns"][-1]["question_id"]
    r1 = agent.submit(text="I would check the logs.", duration_s=10)
    assert r1["next"]["question_id"] == first and r1["next"]["is_follow_up"]
    r2 = agent.submit(text="I would also look at memory.", duration_s=10)
    assert r2["next"]["question_id"] != first and not r2["next"]["is_follow_up"]


def test_every_must_have_skill_is_covered_before_the_interview_ends(agent):
    musts = agent._must_haves()
    res = agent.submit(text="x", duration_s=1)
    while not res["done"]:
        res = agent.submit(text="I would check the logs and what changed.", duration_s=10)
    assert musts <= {a["skill"] for a in res["scorecard"]["answers"]}


def test_no_skill_is_asked_more_than_three_times_in_any_interview(agent):
    res = agent.submit(text="I would check the logs.", duration_s=10)
    while not res["done"]:
        res = agent.submit(text=strong_answer(agent) if len(agent.session.state["turns"]) % 2 else "I would check the logs.", duration_s=10)
    counts = agent._skill_counts()
    assert counts and max(counts.values()) <= MAX_PER_SKILL


def test_the_plan_always_contains_every_must_have_skill(invited, db):
    from app.interview.bank import build_plan

    req = db.get(Requisition, 1)
    musts = {i["skill"] for i in req.rubric["items"] if i["must_have"]}
    for cid in (1, 2, 3):
        assert musts <= {p.skill for p in build_plan(db, cid, req).items}


def test_the_scoring_prompt_has_the_transcript_text_only_and_no_name(agent, db):
    agent.submit(text="I would check the load with top, then memory and swap, then the disk and the logs.", duration_s=10)
    cand = db.get(Candidate, 1)
    with OpsSession() as ops:
        call = ops.query(ModelCall).filter(ModelCall.agent == "interviewer", ModelCall.task == "scoring").first()
    assert "<answer>" in call.prompt_user and "check the load with top" in call.prompt_user
    for secret in identity_strings(cand.profile):
        assert secret.lower() not in (call.prompt_system + call.prompt_user).lower()
    assert "audio" not in call.prompt_user.lower() and ".wav" not in call.prompt_user.lower()


def test_state_is_saved_after_every_turn_so_the_interview_resumes(agent, db):
    agent.submit(text="I would check the logs.", duration_s=10)
    db.expire_all()
    s = db.query(InterviewSession).one()
    assert len(s.state["turns"]) == 1 and s.state["turns"][0]["answers"] and s.state["order"] == [0]
    again = InterviewerAgent(db, s)
    assert again.next_prompt()["text"] == s.state["turns"][-1]["asked"][-1]
