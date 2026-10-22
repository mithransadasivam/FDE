"""Day 17 homework, Task 1: find_secrets() spots keys and passwords before they leave."""

from app.guardrails import find_secrets


def test_no_secrets_in_an_ordinary_answer():
    assert (
        find_secrets("A VPN session can stay connected for a maximum of 12 hours [1].")
        == []
    )
    assert find_secrets("") == []


def test_an_api_key_and_a_password_are_found():
    text = "Use key sk-or-v1-0a1b2c3d4e5f6a7b8c9d0e1f2a3b and Password: Winter2026!"
    assert find_secrets(text) == ["api key", "password in text"]


def test_a_private_key_and_a_connection_string_are_found():
    text = "-----BEGIN RSA PRIVATE KEY-----\nMIIE...\npostgres://report:S3cret@db.example.com/helpdesk"
    assert find_secrets(text) == ["private key", "connection string"]


def test_the_order_is_the_pattern_order():
    text = "postgres://a:b@host/db then pwd=hunter2"
    assert find_secrets(text) == ["password in text", "connection string"]
