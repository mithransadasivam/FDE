"""Takes the README screenshots with a real browser (Playwright) from a running, seeded app.

    python -m scripts.run_journey --reset        (seed it)
    uvicorn app.main:app --port 8002             (run it, in another terminal)
    python -m scripts.take_screenshots --url http://127.0.0.1:8002

Writes PNGs to docs/screenshots/. Fictional data only.
"""
import argparse
import sqlite3
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("docs/screenshots")


def ids(db_path: str) -> dict:
    c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    q = lambda sql: (c.execute(sql).fetchone() or [None])[0]  # noqa: E731
    return {
        "decision": q("select candidate_id from final_decisions order by id limit 1"),
        "forbidden": q("select id from candidates where cv_name like 'C-004%'"),
        "conflict": q("select id from candidates where cv_name like 'C-011%'"),
        "injected": q("select id from candidates where cv_name like 'C-027%'"),
        "invited_token": q("select access_token from candidates where stage='AI_INTERVIEW' limit 1"),
        "person_token": q("select c.access_token from candidates c join interview_sessions s on s.candidate_id=c.id where s.status='PERSON_REQUESTED' limit 1"),
        "screened_token": q("select access_token from candidates where stage='SCREENED' limit 1"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8002")
    ap.add_argument("--db", default="data/hiring.db")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    i = ids(args.db)
    base = args.url
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page = ctx.new_page()

        def shot(name: str, path: str, full: bool = False, wait: int = 400):
            page.goto(base + path)
            page.wait_for_timeout(wait)
            page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)
            print("saved", name)

        shot("01-sign-in", "/login")
        page.fill("#email", "recruiter@example.com")
        page.fill("#password", "demo-password-1")
        page.click("button[type=submit]")
        page.wait_for_url(base + "/")
        shot("02-overview", "/")
        shot("03-requisition-rubric", "/requisitions/1", full=True)
        shot("04-screening-shortlist", "/screening/1", full=True)
        shot("05-candidate-evidence", f"/candidates/{i['injected']}?blind=1", full=True)
        shot("06-pipeline", "/pipeline", full=True)
        shot("07-scorecard", f"/scorecard/{i['decision']}", full=True)
        page.goto(base + "/assistant")
        page.get_by_test_id("question").fill("Who has run Kubernetes in production?")
        page.get_by_test_id("ask-btn").click()
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / "08-assistant.png"))
        print("saved 08-assistant")
        shot("09-outbox", "/outbox", full=True)
        shot("10-compliance", "/compliance")
        shot("11-trust-and-cost", "/trust", full=True)
        shot("12-demo-mode", "/demo", full=True)
        # the copilot: replay the forbidden-question recording instantly
        page.goto(f"{base}/copilot/{i['forbidden']}")
        page.wait_for_timeout(300)
        if page.get_by_test_id("start-replay").count():
            page.select_option("#speed", "0")
            page.get_by_test_id("start-replay").click()
            page.get_by_test_id("draft").wait_for(state="visible", timeout=20000)
            page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "13-copilot-forbidden-question.png"), full_page=True)
        print("saved 13-copilot-forbidden-question")
        # candidate side (signed out)
        pub = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
        for name, path in (("14-open-jobs", "/jobs"), ("15-apply-with-ai-notice", "/jobs/1"), ("16-candidate-status", f"/me/{i['screened_token']}"),
                           ("17-ai-interview-notice", f"/interview/{i['invited_token'] or i['person_token']}")):
            pub.goto(base + path)
            pub.wait_for_timeout(400)
            pub.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
            print("saved", name)
        # the interview page in action: start and show the first question with a diagram
        pub.goto(f"{base}/interview/{i['invited_token'] or i['person_token']}")
        # phone width
        m = b.new_context(viewport={"width": 390, "height": 800}, device_scale_factor=2).new_page()
        m.goto(base + "/jobs/1")
        m.wait_for_timeout(300)
        m.screenshot(path=str(OUT / "18-mobile-job-page.png"), full_page=False)
        print("saved 18-mobile-job-page")
        b.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
