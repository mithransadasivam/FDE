"""The end-of-day Day 3 script: one command runs the day in fake mode and prints what the guide lists."""
from scripts import day2_demo, day3_demo
from tests.test_day2_demo import FILES


def test_day3_demo_runs_the_day_and_prints_the_guides_list(platform, db, capsys):
    for f in FILES + ["C-027_cv.pdf"]:
        platform.apply(f)
    db.expire_all()
    assert day2_demo.main() == 0
    capsys.readouterr()
    assert day3_demo.main() == 0
    out = capsys.readouterr().out
    for needle in ("Security flags on record", "hidden text", "cv-plain", "stopped", "WITHOUT wrapping", "NOT STOPPED", "CHECKED", "practice recruiter interview", "planned moment forbidden_question",
                   "Transcript:", "Warnings (forbidden questions)", "ms after the question ended", "Suggestions (one technical, one behavioural)", "Points heard", "CV conflict cards",
                   "Recruiter scoring page", "Outbox:", "Replay room", "Day 3 demo complete"):
        assert needle in out, needle
