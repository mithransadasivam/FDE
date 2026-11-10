"""Ticket ENG-501: the Bedrock client. botocore's Stubber checks the exact Converse request, with no AWS call."""

import boto3
import pytest
from botocore.stub import ANY, Stubber

from app.llm import BedrockClient, GuardrailBlocked, LLMError, ask_json
from app.prototype.models import ExtractionReply

MODEL = "anthropic.claude-sonnet-5"
REPLY = '{"fields": [{"name": "full_name", "value": "Ms Ananya R. Mehta", "word_ids": ["w003"]}]}'


def runtime():
    rt = boto3.client("bedrock-runtime", region_name="eu-west-2", aws_access_key_id="test", aws_secret_access_key="test")
    return rt, Stubber(rt)


def response(text=REPLY, stop="end_turn", inp=1200, out=240):
    return {"output": {"message": {"role": "assistant", "content": [{"text": text}]}}, "stopReason": stop,
            "usage": {"inputTokens": inp, "outputTokens": out, "totalTokens": inp + out}, "metrics": {"latencyMs": 1500}}


def expected(guardrail=None, messages=None):
    req = {"modelId": MODEL, "system": [{"text": "SYSTEM"}],
           "messages": messages or [{"role": "user", "content": [{"text": "OCR words"}]}],
           "inferenceConfig": {"temperature": 0, "maxTokens": 2000}}
    if guardrail:
        req["guardrailConfig"] = guardrail
    return req


def test_request_without_guardrail():
    c = BedrockClient(None, MODEL)
    assert c.request("SYSTEM", [{"role": "user", "content": "OCR words"}]) == expected()


def test_request_with_guardrail():
    c = BedrockClient(None, MODEL, "gr-abc123", "2")
    assert c.request("SYSTEM", [{"role": "user", "content": "OCR words"}])["guardrailConfig"] == \
        {"guardrailIdentifier": "gr-abc123", "guardrailVersion": "2", "trace": "enabled"}


def test_complete_sends_the_request_and_returns_the_text():
    rt, st = runtime()
    st.add_response("converse", response(), expected())
    with st:
        assert BedrockClient(rt, MODEL).complete("SYSTEM", [{"role": "user", "content": "OCR words"}]) == REPLY
    st.assert_no_pending_responses()


def test_complete_joins_text_blocks():
    rt, st = runtime()
    r = response()
    r["output"]["message"]["content"] = [{"text": '{"fields": '}, {"text": "[]}"}]
    st.add_response("converse", r, expected())
    with st:
        assert BedrockClient(rt, MODEL).complete("SYSTEM", [{"role": "user", "content": "OCR words"}]) == '{"fields": []}'


def test_complete_records_usage():
    rt, st = runtime()
    st.add_response("converse", response(inp=1184, out=236), expected())
    c = BedrockClient(rt, MODEL)
    with st:
        c.complete("SYSTEM", [{"role": "user", "content": "OCR words"}])
    assert c.calls == [{"input_tokens": 1184, "output_tokens": 236, "latency_ms": 1500, "stop_reason": "end_turn"}]


def test_guardrail_intervened_raises():
    rt, st = runtime()
    st.add_response("converse", response("The extracted fields were withheld.", stop="guardrail_intervened"),
                    expected({"guardrailIdentifier": "gr-abc123", "guardrailVersion": "2", "trace": "enabled"}))
    with st, pytest.raises(GuardrailBlocked) as e:
        BedrockClient(rt, MODEL, "gr-abc123", "2").complete("SYSTEM", [{"role": "user", "content": "OCR words"}])
    assert e.value.where == "reply" and "withheld" in e.value.message


def test_access_denied_becomes_a_clear_error():
    rt, st = runtime()
    st.add_client_error("converse", service_error_code="AccessDeniedException", service_message="You don't have access to the model",
                        http_status_code=403, expected_params=expected())
    with st, pytest.raises(LLMError) as e:
        BedrockClient(rt, MODEL).complete("SYSTEM", [{"role": "user", "content": "OCR words"}])
    assert "AccessDeniedException" in str(e.value) and "eu-west-2" in str(e.value)


def test_ask_json_retries_once_through_bedrock():
    rt, st = runtime()
    st.add_response("converse", response("not json"), expected())
    retry = [{"role": "user", "content": [{"text": "OCR words"}]}, {"role": "assistant", "content": [{"text": "not json"}]},
             {"role": "user", "content": [{"text": ANY}]}]
    st.add_response("converse", response(REPLY), expected(messages=retry))
    c = BedrockClient(rt, MODEL)
    with st:
        reply = ask_json(c, "SYSTEM", "OCR words", ExtractionReply, task="x")
    assert reply.fields[0].value == "Ms Ananya R. Mehta" and len(c.calls) == 2
