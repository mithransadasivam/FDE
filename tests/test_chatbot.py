from app.chatbot import SYSTEM, ask
from tests.fakes import FakeClient, bad_key, rate_limit, timeout

HISTORY = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "hi"}]


def no_sleep(seconds):
    return None


def no_log(*args):
    return 0


def test_returns_the_reply():
    backends = {"hosted": (FakeClient("hello"), "m")}
    assert ask(backends, "hosted", HISTORY, sleep=no_sleep, log=no_log) == "hello"


def test_logs_every_successful_call():
    logged = []
    backends = {"hosted": (FakeClient("hello"), "m")}
    ask(backends, "hosted", HISTORY, sleep=no_sleep, log=lambda *a: logged.append(a))
    assert len(logged) == 1 and logged[0][0] == "m"


def test_bad_key_stops_without_retrying():
    hosted = FakeClient(bad_key())
    reply = ask(
        {"hosted": (hosted, "m")}, "hosted", HISTORY, sleep=no_sleep, log=no_log
    )
    assert "key" in reply.lower()
    assert len(hosted.calls) == 1


def test_retries_with_doubling_wait_then_succeeds():
    waits = []
    hosted = FakeClient(rate_limit(), timeout(), "ok")
    reply = ask(
        {"hosted": (hosted, "m")}, "hosted", HISTORY, sleep=waits.append, log=no_log
    )
    assert reply == "ok"
    assert waits == [1, 2]


def test_falls_back_to_local_after_retries():
    backends = {
        "hosted": (FakeClient(rate_limit()), "m"),
        "local": (FakeClient("from local"), "l"),
    }
    assert ask(backends, "hosted", HISTORY, sleep=no_sleep, log=no_log) == "from local"


def test_nothing_reachable():
    backends = {"local": (FakeClient(timeout()), "l")}
    assert (
        ask(backends, "local", HISTORY, sleep=no_sleep, log=no_log)
        == "No model is reachable right now."
    )
