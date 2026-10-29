"""The end-of-day script: one command runs the whole of Day 2 in fake mode and prints what the guide lists."""
from scripts import day2_demo

FILES = [f"C-0{n:02d}_cv.{ext}" for n, ext in [(1, "pdf"), (2, "pdf"), (4, "docx"), (5, "docx"), (6, "pdf"), (7, "pdf"), (8, "docx"), (9, "pdf"), (11, "docx"), (12, "docx")]]


def test_day2_demo_runs_the_whole_day_and_prints_the_guides_list(platform, db, capsys):
    for f in FILES:
        platform.apply(f)
    db.expire_all()
    assert day2_demo.main() == 0
    out = capsys.readouterr().out
    for needle in ("Candidates screened:", "Verified quote rate:", "The recruiter shortlists the top 6", "(opening)", "why:", "level ", "follow-ups", "hints",
                   "overall", "full_conversation.mp3", "decision log entries", "Day 2 demo complete"):
        assert needle.lower() in out.lower(), needle
    assert out.count("move SCREENED -> SHORTLISTED") == 6 and "move SHORTLISTED -> AI_INTERVIEW" in out
    assert "(strong)" in out and "(weak)" in out
