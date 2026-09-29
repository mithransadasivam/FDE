from app.chatbot import build_backends, describe_backends, prices_for

ENV = {
    "BACKENDS": "hosted, strong ,local",
    "OPENROUTER_API_KEY": "sk-test",
    "HOSTED_BASE_URL": "https://openrouter.ai/api/v1",
    "HOSTED_KEY_VAR": "OPENROUTER_API_KEY",
    "HOSTED_MODEL": "anthropic/claude-haiku-4.5",
    "HOSTED_IN_PRICE": "1.00",
    "HOSTED_OUT_PRICE": "5.00",
    "STRONG_BASE_URL": "https://openrouter.ai/api/v1",
    "STRONG_KEY_VAR": "OPENROUTER_API_KEY",
    "STRONG_MODEL": "anthropic/claude-sonnet-4.5",
    "STRONG_IN_PRICE": "3.00",
    "STRONG_OUT_PRICE": "15.00",
    "LOCAL_BASE_URL": "http://localhost:11434/v1",
    "LOCAL_KEY_VAR": "OLLAMA_KEY",
    "LOCAL_MODEL": "llama3.2",
}


def test_registry_loads_all_three_backends_from_env(monkeypatch):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    backends = build_backends()
    assert list(backends) == ["hosted", "strong", "local"]
    assert backends["strong"].model == "anthropic/claude-sonnet-4.5"
    assert (backends["strong"].in_price, backends["strong"].out_price) == (3.0, 15.0)
    assert (backends["hosted"].in_price, backends["hosted"].out_price) == (1.0, 5.0)
    assert (backends["local"].in_price, backends["local"].out_price) == (0.0, 0.0)
    assert str(backends["strong"].client.base_url).startswith("https://openrouter.ai")
    assert str(backends["local"].client.base_url).startswith("http://localhost:11434")


def test_models_listing_shows_id_and_prices():
    backends = build_backends(ENV)
    lines = describe_backends(backends)
    assert len(lines) == 3
    assert "anthropic/claude-sonnet-4.5" in lines[1] and "$15" in lines[1]


def test_prices_looked_up_by_model_id():
    assert prices_for("anthropic/claude-sonnet-4.5", build_backends(ENV)) == (3.0, 15.0)
    assert prices_for("unknown", build_backends(ENV)) == (0.0, 0.0)
