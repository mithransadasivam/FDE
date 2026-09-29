from app.chat_once import build_messages, call_cost


def test_system_message_comes_first():
    messages = build_messages("be brief", "hello?")
    assert messages == [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "hello?"},
    ]


def test_cost_uses_prices_per_million_tokens():
    assert call_cost(1_000_000, 1_000_000, 1.0, 5.0) == 6.0
    assert round(call_cost(500, 100, 1.0, 5.0), 6) == 0.001
