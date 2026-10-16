"""Phase 2 checkpoint: a unit test for each tool (with its error messages) on a temporary database, and a search of
every tool result for an account number."""
import csv
import json

import pytest

from vendor_desk import config, documents
from vendor_desk.tools import Toolbox


@pytest.fixture
def tb(db):
    return Toolbox(db_path=db)


def test_every_tool_has_a_schema_and_says_what_it_does_not_do(tb):
    for spec in tb.specs.values():
        assert spec.parameters["type"] == "object" and spec.parameters["additionalProperties"] is False
        assert spec.read_only
        assert "not" in spec.description.lower() or "never" in spec.description.lower(), spec.name
    assert {"read_request", "find_vendor", "screen_watchlist", "check_documents", "check_payment_terms",
            "check_bank_country", "lookup_policy"} <= set(tb.specs)


def test_read_request(tb):
    r = tb.call("read_request", {"request_id": "REQ-001"})
    assert r["from"] == "it-ops@example.com" and len(r["attachments"]) == 2 and "Tessaro" in r["email_text"]
    assert r["injection_scan"]["suspicious"] is False
    bad = tb.call("read_request", {"request_id": "REQ-011"})["injection_scan"]
    assert bad["suspicious"] and "email" in bad["found_in"]
    doc = tb.call("read_request", {"request_id": "REQ-017"})["injection_scan"]
    assert doc["suspicious"] and any("insurance_certificate" in w for w in doc["found_in"])


def test_read_request_errors_are_readable(tb):
    assert "not a valid request id" in tb.call("read_request", {"request_id": "banana"})["error"] or \
        "pattern" in tb.call("read_request", {"request_id": "banana"})["error"].lower()
    assert "no request file" in tb.call("read_request", {"request_id": "REQ-999"})["error"]
    assert "required" in tb.call("read_request", {})["error"].lower()
    assert "Unknown tool" in tb.call("delete_everything", {})["error"]
    assert "must be a JSON object" in tb.call("read_request", "REQ-001")["error"]


def test_get_vendor(tb):
    v = tb.call("get_vendor", {"vendor_id": "VEN-1010"})
    assert v["name"] == "Brightpath Software Ltd" and v["payment_terms_days"] == 60 and v["bank_country"] == "GB"
    assert "no vendor VEN-9999" in tb.call("get_vendor", {"vendor_id": "VEN-9999"})["error"]
    assert "pattern" in tb.call("get_vendor", {"vendor_id": "1010"})["error"].lower()


def test_find_vendor_duplicate_by_tax_id_even_with_a_different_name(tb):
    r = tb.call("find_vendor", {"name": "Harrowgate Facilities Management Limited", "tax_id": "GB-TX-310442"})
    assert r["result"] == "duplicate" and r["policy_section"] == "§3.1" and r["matches"][0]["vendor_id"] == "VEN-1001"
    # the name alone is below the possible-duplicate score: a name-only check would miss it
    assert tb.call("find_vendor", {"name": "Harrowgate Facilities Management Limited"})["result"] == "none"


def test_find_vendor_possible_duplicate_and_none(tb):
    r = tb.call("find_vendor", {"name": "Corvane Print Services Ltd", "tax_id": "GB-TX-557310"})
    assert r["result"] == "possible_duplicate"
    r = tb.call("find_vendor", {"name": "Tessaro Cloud Backup Ltd"})
    assert r["result"] == "none" and "closest" in r["evidence"]
    assert tb.call("find_vendor", {"name": "Brightpath Software Limited"})["result"] == "duplicate"  # suffix spelling
    assert "pattern" in tb.call("find_vendor", {"name": "X Ltd", "tax_id": "12345"})["error"].lower()


def test_screen_watchlist(tb):
    assert tb.call("screen_watchlist", {"name": "Northern Meridian Trading Ltd"})["result"] == "hit"
    near = tb.call("screen_watchlist", {"name": "Veltrax Marine Supply Ltd"})
    assert near["result"] == "near_match" and near["policy_section"] == "§4.2"
    assert tb.call("screen_watchlist", {"name": "Pennine Stationery Supplies Ltd"})["result"] == "clear"
    assert "short" in tb.call("screen_watchlist", {"name": ""})["error"]


def test_check_documents_missing_expired_and_complete(tb):
    ok = tb.call("check_documents", {"request_ids": ["REQ-002"]})
    assert ok["result"] == "pass" and ok["tax_id"] == "GB-TX-771204" and ok["registered_country"] == "GB"
    miss = tb.call("check_documents", {"request_ids": ["REQ-001"]})
    assert miss["missing"] == ["insurance_certificate"] and miss["policy_section"] == "§2.3"
    exp = tb.call("check_documents", {"request_ids": ["REQ-007"]})
    assert exp["expired"] == ["insurance_certificate"] and "expired on 2026-03-31" in json.dumps(exp)
    two = tb.call("check_documents", {"request_ids": ["REQ-012"]})
    assert two["missing"] == ["tax_registration", "bank_letter"]
    thread = tb.call("check_documents", {"request_ids": ["REQ-001", "REQ-001-R1"]})
    assert thread["result"] == "pass"
    assert "error" in tb.call("check_documents", {"request_ids": []})


def test_check_payment_terms(tb):
    assert tb.call("check_payment_terms", {"days": 45})["result"] == "pass"
    r = tb.call("check_payment_terms", {"days": 60})
    assert r["result"] == "fail" and r["policy_section"] == "§5.1"
    assert "maximum" in tb.call("check_payment_terms", {"days": 9999})["error"]
    assert "integer" in tb.call("check_payment_terms", {"days": "thirty"})["error"]


def test_check_spend_threshold(tb):
    assert tb.call("check_spend_threshold", {"amount_gbp": 2100, "period": "month"})["approvers_required"] == 2
    assert tb.call("check_spend_threshold", {"amount_gbp": 24500, "period": "year"})["approvers_required"] == 1
    assert tb.call("check_spend_threshold", {"amount_gbp": 25000, "period": "year"})["approvers_required"] == 1
    assert tb.call("check_spend_threshold", {"amount_gbp": 25001, "period": "year"})["approvers_required"] == 2
    assert "is not one of" in tb.call("check_spend_threshold", {"amount_gbp": 5, "period": "week"})["error"]


def test_check_bank_country(tb):
    ok = tb.call("check_bank_country", {"request_ids": ["REQ-002"]})
    assert ok["result"] == "pass" and ok["same_country"] and ok["account_holder_matches_legal_name"]
    mt = tb.call("check_bank_country", {"request_ids": ["REQ-006"]})
    assert mt["result"] == "review" and mt["bank_country"] == "MT" and mt["registered_country"] == "GB"
    assert tb.call("check_bank_country", {"request_ids": ["REQ-015"]})["account_used_by_other_vendor"] == "VEN-1019"
    assert tb.call("check_bank_country", {"request_ids": ["REQ-018"]})["account_holder_matches_legal_name"] is False
    assert tb.call("check_bank_country", {"request_ids": ["REQ-012"]})["result"] == "missing"
    # the same company under another spelling is not "another vendor"
    assert tb.call("check_bank_country", {"request_ids": ["REQ-003"]})["account_used_by_other_vendor"] is None


def test_lookup_policy(tb):
    assert "0.95" in tb.call("lookup_policy", {"section": "§3.1"})["text"]
    assert "45 days" in tb.call("lookup_policy", {"section": "5.1"})["text"]
    whole = tb.call("lookup_policy", {"section": "6"})["text"]
    assert "§6.1" in whole and "§6.2" in whole
    assert "no policy section §42" in tb.call("lookup_policy", {"section": "42"})["error"]
    assert "pattern" in tb.call("lookup_policy", {"section": "three"})["error"].lower()


def test_query_vendor_db_refuses_private_columns(tb):
    ok = tb.call("query_vendor_db", {"sql": "SELECT name FROM vendors WHERE payment_terms_days = 60 ORDER BY name"})
    assert [r[0] for r in ok["rows"]] == ["Brightpath Software Ltd", "Dunmere Security Systems Ltd",
                                          "Ironbridge Fleet Leasing Ltd"]
    err = tb.call("query_vendor_db", {"sql": "SELECT account_number FROM bank_accounts"})
    assert "private" in err["error"].lower()
    assert "Only a single SELECT" in tb.call("query_vendor_db", {"sql": "DROP TABLE vendors; --"})["error"]


def all_account_numbers():
    nums = set()
    with open(config.SEED_DIR / "vendors.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            nums |= {r["account_number"], r["sort_code"]}
    for p in (config.requests_dir() / "attachments").rglob("bank_letter.txt"):
        fields = documents.parse_document(p.read_text(encoding="utf-8"))["fields"]
        nums |= {fields["account_number"], fields["sort_code"]}
    nums.discard("n/a")
    return nums


def test_no_tool_result_contains_an_account_number_or_sort_code(tb):
    secrets = all_account_numbers()
    assert len(secrets) > 30
    blobs = []
    for rid in documents.list_request_ids():
        blobs.append(tb.call("read_request", {"request_id": rid}))
        blobs.append(tb.call("check_documents", {"request_ids": [rid]}))
        blobs.append(tb.call("check_bank_country", {"request_ids": [rid]}))
    for n in range(1001, 1021):
        blobs.append(tb.call("get_vendor", {"vendor_id": f"VEN-{n}"}))
    blobs.append(tb.call("query_vendor_db", {"sql": "SELECT * FROM vendors"}))
    blobs.append(tb.call("query_vendor_db", {"sql": "SELECT * FROM bank_accounts"}))
    text = json.dumps(blobs)
    assert [s for s in secrets if s in text] == []


def test_a_tool_bug_becomes_a_readable_error_not_a_crash(tb, monkeypatch):
    monkeypatch.setattr(tb.specs["check_payment_terms"], "fn", lambda days: 1 / 0)
    assert "failed unexpectedly" in tb.call("check_payment_terms", {"days": 30})["error"]
