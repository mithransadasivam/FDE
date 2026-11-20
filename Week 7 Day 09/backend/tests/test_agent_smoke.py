"""Day 9 smoke tests: CaseFlow Classic, the screen reader and one agent run. They pass before the tickets.
Run: python -m pytest -q tests/test_agent_smoke.py"""

from bank import core
from tests.agentkit import legacy_url, run_agent
from tests.bankkit import bank


def _signed_in(user="tom.reyes"):
    c = bank()
    c.post("/legacy/signin", data={"user": user, "password": "kyc-demo"})
    return c


def test_caseflow_classic_shows_only_cases_in_the_persons_remit():
    c = _signed_in("tom.reyes")
    assert c.get("/legacy/find", params={"ref": "KC-022578"}).url.path == "/legacy/case/KC-022578"
    assert "No case found with reference KC-021805" in c.get("/legacy/find", params={"ref": "KC-021805"}).text
    assert c.get("/legacy/find", params={"ref": "KC-021805"}).status_code == 200
    assert _signed_in("helen.achebe").get("/legacy/case/KC-021805").text.count("Record outcome") == 1


def test_single_sign_on_needs_a_token_for_caseflow():
    good = core.issue("tom.reyes", "caseflow", ["kyc.read", "kyc.write"], "fde-mcp", act={"sub": "fde-mcp"})
    r = bank().post("/legacy/sso", data={"token": good})
    assert r.url.path == "/legacy/menu" and "single sign-on via fde-mcp" in r.text
    wrong = core.issue("tom.reyes", "crm", ["kyc.read"], "fde-mcp")
    assert "Single sign-on failed" in bank().post("/legacy/sso", data={"token": wrong}).text


def test_a_locked_record_saves_nothing_and_confirm_writes_the_history_and_audit():
    c = _signed_in("tom.reyes")
    r = c.post("/legacy/case/KC-020480/outcome", data={"do": "Save", "outcome": "Refer to Financial Crime", "reason": "R04", "note": "x"})
    assert "Record locked by Priya Nair (A01) since 09:12. Your changes were not saved." in r.text
    c.post("/legacy/case/KC-022578/outcome", data={"do": "Save", "outcome": "Request more information", "reason": "R02", "note": "Proof of address."})
    r = c.post("/legacy/case/KC-022578/confirm", data={"do": "Confirm"})
    assert "Outcome recorded" in r.text and "Reference OUT-" in r.text
    log = bank().get("/course/caseflow-log").json()
    assert log["cases"]["KC-022578"] == "WAITING APPLICANT" and log["outcomes"][0]["outcome"] == "Request more information"


def test_the_screen_reader_sees_roles_and_names():
    from app.agent.screen import LegacyScreen, snapshot_text

    s = LegacyScreen(legacy_url())
    try:
        els = s.start(core.issue("tom.reyes", "caseflow", ["kyc.read", "kyc.write"], "fde-mcp", act={"sub": "fde-mcp"}))
        text = snapshot_text(s.title(), els)
        assert 'heading "Main menu"' in text and '[e1] link "Find a case"' in text
    finally:
        s.close()


def test_the_agent_works_kx_1001_end_to_end():
    run = run_agent("KX-1001")
    assert run.status == "recorded", run.stop_reason
    assert run.outcome == "Request more information" and run.reference.startswith("OUT-")
    assert [s.tool for s in run.steps][:4] == ["get_exception", "get_customer", "list_documents", "open_caseflow"]
    out = bank().get("/course/caseflow-log").json()["outcomes"][0]
    assert (out["by"], out["via"], out["reference"]) == ("tom.reyes", "fde-mcp", run.reference)
