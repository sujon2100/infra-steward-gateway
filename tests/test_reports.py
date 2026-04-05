"""
Integration tests for /reports endpoint and workflow engine.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_reports_bank_alpha_allowed() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/reports",
            json={
                "tenant_id": "bank_alpha",
                "scenario": "reporting",
                "report_id": "r1",
                "report_type": "standard",
                "payload": {"text": "hello"},
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["policy_decision"]["allowed"] is True
    assert body["provider_used"] == "StubAIProvider"
    assert body["request_id"]


def test_reports_bank_beta_blocked() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/reports",
            json={
                "tenant_id": "bank_beta",
                "scenario": "reporting",
                "report_id": "r2",
                "report_type": "standard",
                "payload": {"text": "hello"},
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ["blocked", "fallback"]
    assert body["policy_decision"]["allowed"] is False


def test_reports_provider_failure_fallback() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/reports",
            json={
                "tenant_id": "bank_alpha",
                "scenario": "provider_failure",
                "report_id": "r3",
                "report_type": "standard",
                "payload": {"text": "hello", "provider_failure": True},
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fallback"
    assert body["policy_decision"]["allowed"] is True
    assert "error" in body
