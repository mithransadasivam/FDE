from types import SimpleNamespace

import pytest

from app import llm_helper
from app.llm_helper import ask_llm


class FakeClient:
    def __init__(self, reply="  hello  \n"):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._reply = reply

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self._reply)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


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
