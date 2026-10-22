"""Fakes for the Day 12 tests: pretend models for the from-scratch agent and for LangGraph. No real calls."""

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from tests.day11_fakes import (  # noqa: F401  (re-exported)
    FakeToolClient,
    asks,
    says,
    tool_call,
)


class FakeGraphModel(BaseChatModel):
    """A LangChain chat model that returns scripted AIMessages in turn and records what it was sent."""

    replies: list = Field(default_factory=list)
    seen: list = Field(default_factory=list)
    bound: list = Field(default_factory=list)

    def bind_tools(self, tools: Any, **kwargs: Any):
        self.bound.extend(t.name for t in tools)
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.seen.append(list(messages))
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return ChatResult(generations=[ChatGeneration(message=reply)])

    @property
    def _llm_type(self) -> str:
        return "fake-graph-model"


def graph_asks(name, args, call_id="call_1"):
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    )


def graph_says(text):
    return AIMessage(content=text)
