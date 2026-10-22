"""Day 15: tracing. A trace is the record of one request: a tree of spans, one for each step
(retrieve, generate), each with its timing and a few facts about it. Phoenix shows the traces.

Done: setup_tracing() and get_tracer(). With TRACING=1 they send every span to Phoenix and also
trace each OpenAI call automatically (prompt, reply, tokens). Without it, spans go nowhere.
Also done: trace_step() (Activity 3). Check it with tests/test_tracing.py.
"""

import os
from contextlib import contextmanager

from dotenv import load_dotenv
from opentelemetry import trace

load_dotenv()
PROJECT = os.getenv("PHOENIX_PROJECT_NAME", "helpdesk-chatbot")
_ready = False


def setup_tracing() -> None:
    """Call once when the service starts. Does nothing unless TRACING=1."""
    global _ready
    if _ready or os.getenv("TRACING") != "1":
        return
    from phoenix.otel import register

    # PHOENIX_COLLECTOR_ENDPOINT says where Phoenix is, e.g. http://localhost:6006 or http://phoenix:6006
    register(project_name=PROJECT, auto_instrument=True, batch=True, verbose=False)
    _ready = True


def get_tracer():
    return trace.get_tracer("helpdesk-chatbot")


@contextmanager
def trace_step(name: str, tracer=None, **attributes):
    """Record one step of a request as a span.

        with trace_step("retrieve", question_chars=42) as span:
            ...                                   # the step's work
            span.set_attribute("chatbot.chunks", 4)

    Rules (tests/test_tracing.py checks each one):
    - tracer = tracer or get_tracer()
    - start a span called name with tracer.start_as_current_span(name), so a step started inside
      another one becomes its child
    - for each keyword argument whose value is not None: span.set_attribute(f"chatbot.{key}", value)
    - yield the span, so the caller can add attributes once it knows more
    - if the step raises an error: span.set_attribute("chatbot.error_type", type(error).__name__),
      then raise the error again (OpenTelemetry marks the span as failed and records the error)
    """
    tracer = tracer or get_tracer()
    with tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(f"chatbot.{key}", value)
        try:
            yield span
        except Exception as error:
            span.set_attribute("chatbot.error_type", type(error).__name__)
            raise
