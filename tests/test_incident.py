"""Validation-failure tests for IncidentReport: no model and no API calls."""

import pytest
from pydantic import ValidationError

from app.schemas import IncidentReport

VALID = {
    "incident_id": "INC-2026-0917",
    "system": "Payments API",
    "severity": "P1",
    "started_at": "2026-09-14T14:05:00+05:30",
    "resolved_at": "2026-09-14T15:20:00+05:30",
    "impact": "All card payments failed for 75 minutes.",
    "root_cause": "A configuration change pointed the service at the wrong database.",
    "actions": ["Rolled back the deployment", "Added a config check to the pipeline"],
}


def test_a_valid_incident_passes():
    incident = IncidentReport.model_validate(VALID)
    assert incident.severity == "P1" and incident.resolved_at > incident.started_at


def test_unknown_severity_is_rejected():
    with pytest.raises(ValidationError):
        IncidentReport.model_validate({**VALID, "severity": "High"})


def test_resolved_before_started_is_rejected():
    with pytest.raises(ValidationError, match="earlier than started_at"):
        IncidentReport.model_validate(
            {**VALID, "resolved_at": "2026-09-14T13:00:00+05:30"}
        )


def test_badly_formed_incident_id_is_rejected():
    with pytest.raises(ValidationError):
        IncidentReport.model_validate({**VALID, "incident_id": "0917"})


def test_open_incident_needs_no_resolved_at_or_root_cause():
    data = {k: v for k, v in VALID.items() if k not in ("resolved_at", "root_cause")}
    incident = IncidentReport.model_validate(data)
    assert incident.resolved_at is None and incident.root_cause is None


def test_mixed_timezone_is_rejected():
    with pytest.raises(ValidationError, match="timezone"):
        IncidentReport.model_validate({**VALID, "resolved_at": "2026-09-14T15:20:00"})
