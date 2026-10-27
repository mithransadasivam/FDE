def test_health_ready_and_metrics_need_no_sign_in(platform):
    v = platform.visitor
    assert v.get("/health").json() == {"status": "ok"}
    r = v.get("/ready")
    assert r.status_code == 200 and r.json()["status"] == "ready" and r.json()["checks"]["models"] == "fake mode"
    assert "registered" in r.json()["checks"]["agent_tools"]


def test_metrics_report_requests_models_agents_and_candidates(platform):
    platform.apply("C-001_cv.pdf")
    platform.rc.post("/screening/1/run")
    text = platform.visitor.get("/metrics").text
    for name in ("hiring_http_requests_total", "hiring_model_calls_total", "hiring_model_cost_usd_total", "hiring_agent_steps_total",
                 'hiring_candidates{stage="SCREENED"} 1', "hiring_open_findings", "hiring_email_drafts_waiting", "hiring_assistant_questions_total"):
        assert name in text, name
    calls = [ln for ln in text.splitlines() if ln.startswith("hiring_model_calls_total")][0]
    assert int(calls.split()[-1]) >= 3


def test_not_ready_when_a_dependency_is_missing(platform, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "fake_models", False)
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "")
    r = platform.visitor.get("/ready")
    assert r.status_code == 503 and r.json()["checks"]["models"].startswith("error")
