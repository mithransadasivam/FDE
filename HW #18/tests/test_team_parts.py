"""Day 14: the parts that are done (meter and publishing). These pass from the start."""

from types import SimpleNamespace

from app.meter import Meter, label
from app.team import notice_markdown, slug
from tests.day14_fakes import NOTICE, FakeToolClient, says


def test_the_meter_counts_calls_and_tokens_per_agent():
    reply = says("hi")
    client = FakeToolClient(reply)
    meter = Meter(client)
    original = client.chat.completions.create

    def with_usage(**kw):
        r = original(**kw)
        r.usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20)
        return r

    client.chat.completions.create = with_usage
    label(meter, "writer")
    meter.chat.completions.create(model="m", messages=[])
    meter.chat.completions.create(model="m", messages=[])
    label(meter, "reviewer")
    meter.chat.completions.create(model="m", messages=[])
    s = meter.summary()
    assert (s["calls"], s["tokens"]) == (3, 360)
    assert s["by_agent"] == {
        "writer": {"calls": 2, "tokens": 240},
        "reviewer": {"calls": 1, "tokens": 120},
    }


def test_label_ignores_ordinary_clients():
    client = FakeToolClient(says("x"))
    label(client, "writer")
    assert not hasattr(client, "agent")


def test_the_published_notice_format():
    text = notice_markdown(NOTICE, "OK to send")
    assert text.startswith("# Finance Portal unavailable\n\nFor: All staff\n")
    assert "What to do:\n- Follow the IT status page for updates" in text
    assert "Sources: service_status, KB-6601" in text
    assert text.rstrip().endswith("OK to send")
    assert slug("VPN-809: what to do!") == "vpn-809-what-to-do"
