"""Day 15, Activity 3: trace_step() records each step as a span. The spans go to a list in memory."""

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

import app.tracing
from app.tracing import trace_step


@pytest.fixture
def spans(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    monkeypatch.setattr(app.tracing, "get_tracer", lambda: tracer)
    return exporter


def test_a_step_becomes_a_span_with_its_attributes(spans):
    with trace_step("retrieve", question_chars=42, mode="vector", missing=None):
        pass
    [span] = spans.get_finished_spans()
    assert span.name == "retrieve"
    assert dict(span.attributes) == {
        "chatbot.question_chars": 42,
        "chatbot.mode": "vector",
    }


def test_a_step_inside_another_is_its_child(spans):
    with trace_step("ask"), trace_step("retrieve"):
        pass
    child, parent = spans.get_finished_spans()
    assert (child.name, parent.name) == ("retrieve", "ask")
    assert child.parent.span_id == parent.context.span_id


def test_the_caller_can_add_attributes_later(spans):
    with trace_step("retrieve") as span:
        span.set_attribute("chatbot.chunks_kept", 3)
    assert spans.get_finished_spans()[0].attributes["chatbot.chunks_kept"] == 3


def test_an_error_is_recorded_and_raised_again(spans):
    with pytest.raises(TimeoutError), trace_step("generate"):
        raise TimeoutError("the model took too long")
    [span] = spans.get_finished_spans()
    assert span.status.status_code == StatusCode.ERROR
    assert span.attributes["chatbot.error_type"] == "TimeoutError"


def test_one_question_gives_one_trace_with_every_step(spans, fake_chatbot):
    import app.service

    app.service.answer("How long can a VPN session stay connected?")
    names = [s.name for s in spans.get_finished_spans()]
    assert names == ["retrieve", "open_model_stream", "generate", "ask"]
    by_name = {s.name: s for s in spans.get_finished_spans()}
    assert by_name["open_model_stream"].attributes["chatbot.model"] == "fake-primary"
    assert by_name["retrieve"].attributes["chatbot.chunks_kept"] == 1
    assert len({s.context.trace_id for s in spans.get_finished_spans()}) == 1
