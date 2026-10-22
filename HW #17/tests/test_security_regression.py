"""Day 17: security regression tests. Every attack in the class list is run against the fake
chatbot and agent; once your defences are in, these keep them in. They pass when all four
activities are done. C03 (answering like a pirate) is a known, accepted risk: see slide 26."""

from app.red_team import load_attacks, run_attack

ACCEPTED = {"C03"}


def results(guardrails: bool, profile: str) -> dict:
    return {
        a["id"]: run_attack(a, profile=profile, guardrails=guardrails)
        for a in load_attacks()
    }


def test_without_defences_every_attack_works(red_team_env):
    assert all(r["succeeded"] for r in results(False, "wide").values())


def test_with_defences_only_the_accepted_risk_remains(red_team_env, monkeypatch):
    monkeypatch.setenv("GUARDRAILS", "1")
    worked = {i for i, r in results(True, "least").items() if r["succeeded"]}
    assert worked == ACCEPTED


def test_ordinary_questions_still_get_answers(red_team_env, monkeypatch):
    from app import service

    monkeypatch.setenv("GUARDRAILS", "1")
    r = service.answer("How long can a VPN session stay connected?")
    assert r["blocked"] is False and "12 hours" in r["answer"] and r["guardrail"] == []
