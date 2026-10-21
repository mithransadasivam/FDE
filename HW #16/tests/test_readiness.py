"""Day 15, Activity 2: readiness() says whether the service can answer, and why not."""

from fastapi.testclient import TestClient

from app import service
from app.api import api
from app.service import readiness


def test_all_checks_pass_means_ready():
    r = readiness([("a", lambda: (True, "fine")), ("b", lambda: (True, "also fine"))])
    assert r == {
        "ready": True,
        "checks": {
            "a": {"ok": True, "detail": "fine"},
            "b": {"ok": True, "detail": "also fine"},
        },
    }


def test_one_failure_means_not_ready_but_every_check_still_runs():
    ran = []

    def check(name, ok):
        def run():
            ran.append(name)
            return ok, name

        return run

    r = readiness([("key", check("key", False)), ("index", check("index", True))])
    assert r["ready"] is False and ran == ["key", "index"]
    assert (
        r["checks"]["key"] == {"ok": False, "detail": "key"}
        and r["checks"]["index"]["ok"] is True
    )


def test_a_check_that_raises_counts_as_failed_with_its_error():
    def boom():
        raise ConnectionRefusedError("Ollama is not running")

    r = readiness([("ollama", boom), ("key", lambda: (True, "set"))])
    assert r["ready"] is False
    assert r["checks"]["ollama"] == {
        "ok": False,
        "detail": "ConnectionRefusedError: Ollama is not running",
    }
    assert r["checks"]["key"]["ok"] is True


def test_the_fake_chatbot_is_ready_with_the_default_checks(fake_chatbot):
    r = readiness()
    assert r["ready"] is True and list(r["checks"]) == ["mode"]


def test_get_ready_answers_200_or_503(fake_chatbot, monkeypatch):
    client = TestClient(api)
    assert client.get("/ready").status_code == 200
    monkeypatch.setattr(
        service, "default_checks", lambda: [("index", lambda: (False, "no index"))]
    )
    r = client.get("/ready")
    assert r.status_code == 503 and r.json()["checks"]["index"]["detail"] == "no index"
