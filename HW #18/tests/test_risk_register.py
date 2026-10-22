"""Day 18, Activity 4: check_register() finds every problem in the risk register."""

from app.risk_register import check_register, rating


def risk(tmp_path, **changes):
    (tmp_path / "ev.json").write_text("{}")
    r = {
        "id": "R01",
        "title": "Prompt injection",
        "function": "MAP",
        "likelihood": 3,
        "impact": 4,
        "owner": "Product owner",
        "controls": ["Guardrails"],
        "evidence": ["ev.json"],
        "status": "mitigated",
    }
    return {**r, **changes}


def test_a_good_register_passes(tmp_path):
    assert (
        check_register([risk(tmp_path), risk(tmp_path, id="R02")], root=str(tmp_path))
        == []
    )


def test_ratings():
    assert rating(3, 5) == {"score": 15, "level": "high"}
    assert rating(2, 4) == {"score": 8, "level": "medium"}
    assert rating(1, 5) == {"score": 5, "level": "low"}


def test_function_scores_and_duplicate_ids(tmp_path):
    rs = [risk(tmp_path), risk(tmp_path, function="PLAN", likelihood=6)]
    assert check_register(rs, root=str(tmp_path)) == [
        "duplicate id: R01",
        "R01: function must be one of GOVERN, MAP, MEASURE, MANAGE",
        "R01: likelihood and impact must be whole numbers from 1 to 5",
    ]
    assert check_register([risk(tmp_path, impact="4")], root=str(tmp_path)) == [
        "R01: likelihood and impact must be whole numbers from 1 to 5"
    ]


def test_owner_controls_and_status(tmp_path):
    r = risk(tmp_path, owner="", controls=[], status="done")
    assert check_register([r], root=str(tmp_path)) == [
        "R01: needs an owner",
        "R01: needs at least one control",
        "R01: status must be one of open, mitigated, accepted",
    ]


def test_evidence_must_exist(tmp_path):
    assert check_register([risk(tmp_path, evidence=[])], root=str(tmp_path)) == [
        "R01: needs evidence"
    ]
    r = risk(tmp_path, evidence=["ev.json", "logs/gone.json"])
    assert check_register([r], root=str(tmp_path)) == [
        "R01: no evidence at logs/gone.json"
    ]


def test_an_accepted_risk_names_who_and_why(tmp_path):
    r = risk(tmp_path, status="accepted")
    assert check_register([r], root=str(tmp_path)) == [
        "R01: an accepted risk needs accepted_by and a reason"
    ]
    ok = risk(
        tmp_path, status="accepted", accepted_by="Service desk lead", reason="Harmless"
    )
    assert check_register([ok], root=str(tmp_path)) == []
