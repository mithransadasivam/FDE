"""The UI and product pass: notes with mentions (blind-safe), the grouped navigation, search, the inbox, the board's JSON move, the CSV of ticked candidates."""
import json

import pytest

from app.models import Candidate, DecisionLog
from app.models_ext import CandidateNote
from tests.test_interview import invited, shortlisted, token  # noqa: F401


# ---- notes ----------------------------------------------------------------------------------------------------------------------------------------
def test_a_note_is_saved_logged_and_mentions_a_colleague(shortlisted, db):
    r = shortlisted.rc.post("/candidates/1/notes", data={"body": "Strong on networking. @hm can you check Terraform?"})
    assert r.status_code == 303
    db.expire_all()
    n = db.query(CandidateNote).one()
    assert n.author == "recruiter@example.com" and n.mentions == ["hm@example.com"]
    assert db.query(DecisionLog).filter_by(action="note added").one().evidence == {"mentions": ["hm@example.com"]}
    html = shortlisted.hm.get("/candidates/1").text
    assert 'data-testid="notes"' in html and '<span class="mention">@hm</span>' in html and "Strong on networking" in html


def test_an_empty_note_is_refused_and_only_the_author_can_delete(shortlisted, db):
    shortlisted.rc.post("/candidates/1/notes", data={"body": "   "})
    db.expire_all()
    assert db.query(CandidateNote).count() == 0
    shortlisted.rc.post("/candidates/1/notes", data={"body": "first"})
    nid = db.query(CandidateNote).one().id
    assert shortlisted.hm.post(f"/candidates/1/notes/{nid}/delete").status_code == 403
    shortlisted.rc.post(f"/candidates/1/notes/{nid}/delete")
    db.expire_all()
    assert db.query(CandidateNote).count() == 0 and db.query(DecisionLog).filter_by(action="note deleted").count() == 1


def test_notes_are_blind_for_the_hiring_manager_even_if_someone_typed_a_name(shortlisted, db):
    cand = db.get(Candidate, 1)
    name, email = cand.profile["name"]["value"], cand.profile["email"]["value"]
    shortlisted.rc.post("/candidates/1/notes", data={"body": f"Spoke to {name}, write to {email}"})
    hm_page = shortlisted.hm.get("/candidates/1").text
    assert name not in hm_page and email not in hm_page and "Spoke to" in hm_page
    assert name in shortlisted.rc.get("/candidates/1").text  # the recruiter's own view is not blind
    assert name not in shortlisted.rc.get("/candidates/1?blind=1").text


def test_a_note_cannot_inject_html(shortlisted, db):
    shortlisted.rc.post("/candidates/1/notes", data={"body": "<script>alert(1)</script> @hm"})
    html = shortlisted.rc.get("/candidates/1").text
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html


# ---- search ---------------------------------------------------------------------------------------------------------------------------------------
def test_search_finds_candidates_by_number_skill_and_name_and_is_blind_for_the_hiring_manager(shortlisted, db):
    name = db.get(Candidate, 1).profile["name"]["value"]
    assert "Candidate #1" in shortlisted.rc.get("/search?q=1").text or name in shortlisted.rc.get("/search?q=1").text
    assert name.split()[0] in shortlisted.rc.get(f"/search?q={name.split()[0]}").text
    hm = shortlisted.hm.get(f"/search?q={name.split()[0]}").text
    assert name not in hm and "No candidates match" in hm  # a name is never searched in the blind view
    assert "No candidates match" in shortlisted.rc.get("/search?q=zzzznotathing").text
    assert "Candidate #" in shortlisted.hm.get("/search?q=linux").text
    assert shortlisted.visitor.get("/search?q=x").status_code in (303, 401, 403)


# ---- the inbox and the shell --------------------------------------------------------------------------------------------------------------------
def test_the_inbox_shows_what_is_waiting_and_is_for_recruiters(invited):
    html = invited.rc.get("/inbox").text
    assert "Emails to approve" in html and "AI interviews to review" in html and 'class="tabs"' in html and 'href="/outbox"' in html
    assert invited.hm.get("/inbox").status_code == 403


def test_the_bell_counts_what_is_waiting_for_a_recruiter(invited):
    html = invited.rc.get("/").text
    assert 'data-testid="bell"' in html and 'class="dot"' in html and "email draft(s) to approve" in html
    assert 'data-testid="bell"' not in invited.hm.get("/").text


def test_the_pipeline_board_moves_a_card_with_a_json_reply_and_a_refusal_comes_back_in_the_reply(shortlisted, db):
    r = shortlisted.rc.post("/pipeline/move", data={"candidate_id": 1, "to": "WITHDRAWN", "reason": "withdrew", "ajax": 1})
    assert r.json()["ok"] is True and "moved from" in r.json()["message"]
    bad = shortlisted.rc.post("/pipeline/move", data={"candidate_id": 2, "to": "DECISION", "reason": "x", "ajax": 1}).json()
    assert bad["ok"] is False and "Refused" in bad["message"]
    html = shortlisted.rc.get("/pipeline").text
    assert 'draggable="true"' in html and 'id="move-modal"' in html and "Move a candidate" not in html
    assert 'draggable="true"' not in shortlisted.hm.get("/pipeline").text


def test_the_csv_of_ticked_candidates_only_has_those_rows(shortlisted):
    everyone = shortlisted.rc.get("/export/candidates.csv?req=1").text.strip().splitlines()
    two = shortlisted.rc.get("/export/candidates.csv?req=1&ids=1,3").text.strip().splitlines()
    assert len(everyone) == 4 and len(two) == 3 and two[1].startswith("1,") and two[2].startswith("3,")


def test_the_candidate_list_can_be_searched_and_sorted(shortlisted, db):
    asc = shortlisted.rc.get("/candidates?sort=score&dir=asc").text
    desc = shortlisted.rc.get("/candidates?sort=score&dir=desc").text
    assert asc != desc and 'id="compare-bar"' in asc and "Export CSV" in asc
    name = db.get(Candidate, 2).profile["name"]["value"]
    found = shortlisted.rc.get(f"/candidates?q={name.split()[0]}").text
    assert name in found and "match" in found


# ---- scheduling and the email sign-off ----------------------------------------------------------------------------------------------------------
def _ready_for_the_human_interview(invited, db):
    from app.models import Requisition
    from tests.sim.runner import run_interview
    from tests.test_interview import review_form

    run_interview(db, db.get(Candidate, 1), db.get(Requisition, 1), "strong")
    db.expire_all()
    invited.rc.post("/interviews/1/review", data=review_form(db))


def test_the_recruiter_picks_the_time_for_the_human_interview(invited, db):
    from app.agents.communications import free_slots, pretty
    from app.models_ext import EmailDraft

    _ready_for_the_human_interview(invited, db)
    page = invited.rc.get("/interviews/1").text
    assert 'data-testid="slot-picker"' in page
    third = free_slots(8)[2]
    invited.rc.post("/interviews/1/decision", data={"decision": "human_interview", "reason": "strong answers", "slot_id": third["slot_id"]})
    db.expire_all()
    draft = db.query(EmailDraft).filter_by(candidate_id=1, kind="invitation").one()
    assert pretty(third) in draft.body and draft.status == "DRAFT"  # the chosen time, and it still waits for approval
    assert db.get(Candidate, 1).stage == "HUMAN_INTERVIEW"


def test_a_time_that_is_not_free_is_refused_and_nothing_moves(invited, db):
    _ready_for_the_human_interview(invited, db)
    invited.rc.post("/interviews/1/decision", data={"decision": "human_interview", "reason": "strong answers", "slot_id": "S-999"})
    db.expire_all()
    assert db.get(Candidate, 1).stage == "AI_INTERVIEW"
    assert "no longer free" in invited.rc.get("/interviews/1").text


def test_the_email_sign_off_is_a_setting_and_ends_every_draft(invited, db):
    from app.models_ext import EmailDraft

    r = invited.hm.post("/settings", data={"company_name": "Acme Talent", "tagline": "t", "accent": "#4f46e5", "support_email": "careers@example.com", "welcome": "w",
                                           "email_signoff": "Kind regards,\nThe Acme talent team"})
    assert r.status_code == 303
    _ready_for_the_human_interview(invited, db)
    invited.rc.post("/interviews/1/decision", data={"decision": "human_interview", "reason": "strong answers"})
    db.expire_all()
    body = db.query(EmailDraft).filter_by(candidate_id=1, kind="invitation").one().body
    assert body.rstrip().endswith("Kind regards,\nThe Acme talent team")
    blank = invited.hm.post("/settings", data={"company_name": "Acme Talent", "tagline": "t", "accent": "#4f46e5", "support_email": "", "welcome": "w", "email_signoff": "  "})
    assert blank.status_code == 303 and "Best wishes," in invited.hm.get("/settings").text  # an empty sign-off falls back to the default: every email still ends with one
    from app import branding

    branding.clear_cache()


# ---- the older approval flow and the demo page are gone -----------------------------------------------------------------------------------
def test_deleting_is_the_candidates_own_act_and_the_deletions_page_is_only_a_record(invited, db):
    t = token(db)
    assert invited.visitor.post(f"/me/{t}/delete-request").status_code in (404, 405)  # nothing waits for a recruiter any more
    invited.visitor.post(f"/me/{t}/delete", data={"confirm": "yes"})
    page = invited.rc.get("/data-requests").text
    assert 'data-testid="requests"' in page and "candidate (self-service)" in page and "<form" not in page.split('data-testid="requests"')[1]
    assert invited.rc.post("/data-requests/1/decide", data={"decision": "approve", "reason": "x"}).status_code in (404, 405)
    assert invited.hm.get("/data-requests").status_code == 403


def test_the_demo_page_and_its_menu_item_are_gone(invited):
    assert invited.rc.get("/demo").status_code == 404
    assert "Demo mode" not in invited.rc.get("/").text


def test_the_overview_leads_with_what_is_waiting_and_lists_the_jobs(invited):
    html = invited.rc.get("/").text
    assert 'data-testid="waiting"' in html and 'class="tile' in html and "jobs-grid" in html and "Cloud Support Engineer" in html
    assert "Recent activity" not in html and "decision log" in html
    hm = invited.hm.get("/").text
    assert "Rubrics to approve" in hm and "Waiting for you" not in hm
