"""Activity 2: schema_text() describes the database without the hidden columns.
Run: pytest tests/test_mcp_schema.py"""

from app.mcp_server import build_server, schema_text
from tests.day13_helpers import call_tool, with_client


def test_starts_with_the_title_and_ends_with_the_privacy_line(db):
    lines = schema_text(db).split("\n")
    assert lines[0] == "# Help desk database"
    assert lines[-2:] == ["", "Personal staff data is not available."]


def test_one_heading_per_table_in_name_order_with_row_counts(db):
    headings = [line for line in schema_text(db).split("\n") if line.startswith("## ")]
    assert headings == [
        "## assets (12 rows)",
        "## staff (24 rows)",
        "## tickets (40 rows)",
    ]


def test_lists_columns_with_their_types(db):
    text = schema_text(db)
    assert "\n## tickets (40 rows)\n- id (TEXT)\n- created (TEXT)\n" in text
    assert "- work_email (TEXT)" in text and "- purchase_date (TEXT)" in text


def test_hidden_columns_are_not_listed(db):
    text = schema_text(db)
    for column in ("personal_mobile", "home_address", "date_of_birth"):
        assert column not in text


def test_the_resource_and_the_tool_return_the_same_text(db):
    server = build_server(db)
    listed = with_client(server, lambda c: c.list_resources())
    assert [r.uri for r in listed.resources] == ["helpdesk://schema"]
    read = with_client(server, lambda c: c.read_resource("helpdesk://schema"))
    assert read.contents[0].text == schema_text(db)
    assert call_tool(server, "describe_database").content[0].text == schema_text(db)
