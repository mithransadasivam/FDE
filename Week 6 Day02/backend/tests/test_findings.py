"""Ticket ENG-101: findings with evidence. 9 tests."""

import json

from fastapi.testclient import TestClient

from app.config import TRANSCRIPT_FILE
from app.discovery.findings import extract_findings, verify_evidence
from app.discovery.models import Finding
from app.main import app
from tests.fakes import FakeClient

TRANSCRIPT = TRANSCRIPT_FILE.read_text(encoding="utf-8")


def finding(quote, speaker="Tom", fid="F01", kind="pain_point"):
    return Finding(id=fid, kind=kind, title="A finding", detail="Some detail here", speaker=speaker, quote=quote)


def reply(*items):
    return json.dumps({"findings": [
        {"kind": "constraint", "title": t, "detail": "Detail text", "speaker": "Helen", "quote": q} for t, q in items]})


def test_extract_numbers_findings_in_order():
    client = FakeClient(reply(("First", "Customer documents must not leave the UK."), ("Second", "nothing goes to public AI chat tools")))
    out = extract_findings(TRANSCRIPT, client)
    assert [f.id for f in out] == ["F01", "F02"]
    assert [f.title for f in out] == ["First", "Second"]
    assert all(f.evidence_ok is None and f.review == "unreviewed" for f in out)


def test_extract_sends_the_transcript():
    client = FakeClient(reply(("One", "Customer documents must not leave the UK.")))
    extract_findings(TRANSCRIPT, client)
    sent = " ".join(m["content"] for m in client.requests[0]["messages"])
    assert "4,200 documents waiting" in sent


def test_extract_retries_once_on_invalid_reply():
    client = FakeClient('{"findings": "not a list"}', reply(("One", "Customer documents must not leave the UK.")))
    assert len(extract_findings(TRANSCRIPT, client)) == 1
    assert len(client.requests) == 2


def test_exact_quote_is_verified():
    out = verify_evidence([finding("CaseFlow has an API, but it's read-only for us.")], TRANSCRIPT)
    assert out[0].evidence_ok is True


def test_case_spaces_and_curly_quotes_are_ignored():
    q = "caseflow has an API,   but it’s READ-ONLY for us"
    assert verify_evidence([finding(q)], TRANSCRIPT)[0].evidence_ok is True


def test_invented_quote_fails():
    q = "Every January we get twice as many applications as we can handle."
    assert verify_evidence([finding(q, speaker="Deborah")], TRANSCRIPT)[0].evidence_ok is False


def test_right_words_wrong_speaker_fails():
    q = "CaseFlow has an API, but it's read-only for us."
    assert verify_evidence([finding(q, speaker="Deborah")], TRANSCRIPT)[0].evidence_ok is False


def test_keeps_every_finding_in_order():
    fs = [finding("Customer documents must not leave the UK.", "Helen", "F01"),
          finding("I made this up entirely, it is not there", "Tom", "F02"),
          finding("CaseFlow has an API, but it's read-only for us.", "Tom", "F03")]
    out = verify_evidence(fs, TRANSCRIPT)
    assert [f.id for f in out] == ["F01", "F02", "F03"]
    assert [f.evidence_ok for f in out] == [True, False, True]


def test_api_extracts_and_flags_two_bad_quotes():
    api = TestClient(app)
    data = api.post("/api/findings/extract").json()
    assert len(data) >= 10
    bad = [f["title"] for f in data if f["evidence_ok"] is False]
    assert bad == ["January peak doubles volume", "Back inside three days before January"]
