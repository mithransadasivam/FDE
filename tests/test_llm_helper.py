import logging
from types import SimpleNamespace

import pytest

from app import llm_helper
from app.llm_helper import ask_llm


class FakeClient:
    def __init__(self, reply="  hello  \n", total_tokens=None):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._reply = reply
        self._total_tokens = total_tokens

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self._reply)
        response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
        if self._total_tokens is not None:
            response.usage = SimpleNamespace(total_tokens=self._total_tokens)
        return response


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    monkeypatch.setattr(llm_helper, "load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


def test_returns_stripped_reply():
    assert ask_llm("hi", model="m", client=FakeClient()) == "hello"


def test_sends_single_user_message_with_defaults():
    client = FakeClient()
    ask_llm("what is 2+2?", model="test/model", client=client)
    call = client.calls[0]
    assert call["model"] == "test/model"
    assert call["temperature"] == 0.2
    assert call["messages"] == [{"role": "user", "content": "what is 2+2?"}]


def test_custom_temperature():
    client = FakeClient()
    ask_llm("hi", model="m", temperature=0.9, client=client)
    assert client.calls[0]["temperature"] == 0.9


def test_default_model_from_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "env/model")
    client = FakeClient()
    ask_llm("hi", client=client)
    assert client.calls[0]["model"] == "env/model"


def test_explicit_model_overrides_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "env/model")
    client = FakeClient()
    ask_llm("hi", model="explicit/model", client=client)
    assert client.calls[0]["model"] == "explicit/model"


def test_missing_model_raises():
    with pytest.raises(RuntimeError, match="LLM_MODEL"):
        ask_llm("hi", client=FakeClient())


@pytest.mark.parametrize("prompt", ["", "   ", "\n\t", None])
def test_empty_prompt_raises_value_error(prompt):
    with pytest.raises(ValueError):
        ask_llm(prompt, model="m", client=FakeClient())


def test_missing_api_key_raises_clear_error():
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        ask_llm("hi", model="m")


def test_api_key_not_required_when_client_given():
    assert ask_llm("hi", model="m", client=FakeClient("ok")) == "ok"


def test_none_content_returns_empty_string():
    assert ask_llm("hi", model="m", client=FakeClient(reply=None)) == ""


def test_logs_model_latency_and_tokens(caplog):
    caplog.set_level(logging.INFO, logger="app.llm_helper")
    client = FakeClient(reply="secret reply", total_tokens=42)
    ask_llm("secret prompt", model="test/model", client=client)
    records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert len(records) == 1
    message = records[0].getMessage()
    assert "model=test/model" in message
    assert "latency_ms=" in message
    assert "total_tokens=42" in message
    assert "secret prompt" not in caplog.text
    assert "secret reply" not in caplog.text


def test_logs_error_and_reraises(caplog):
    caplog.set_level(logging.INFO, logger="app.llm_helper")
    client = FakeClient()

    def boom(**kwargs):
        raise RuntimeError("boom")

    client.chat.completions.create = boom
    with pytest.raises(RuntimeError, match="boom"):
        ask_llm("secret prompt", model="test/model", client=client)
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "test/model" in errors[0].getMessage()
    assert "secret prompt" not in caplog.text


class BoomError(Exception):
    pass


def test_client_exception_is_logged_as_error_and_reraised(caplog):
    client = FakeClient()

    def boom(**kwargs):
        raise BoomError("api down")

    client.chat.completions.create = boom
    with caplog.at_level(logging.ERROR, logger="app.llm_helper"), pytest.raises(BoomError):
        ask_llm("hi", model="test/model", client=client)
    assert any(r.levelno == logging.ERROR for r in caplog.records)


def test_model_returning_none_gives_empty_string_not_crash():
    result = ask_llm("hi", model="m", client=FakeClient(reply=None))
    assert result == ""


def test_prompt_of_only_spaces_raises_value_error():
    with pytest.raises(ValueError):
        ask_llm("     ", model="m", client=FakeClient())
