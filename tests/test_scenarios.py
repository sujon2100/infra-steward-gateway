from fastapi.testclient import TestClient

from app.main import app


def test_scenario_bank_alpha_compliant() -> None:
    with TestClient(app) as client:
        response = client.get("/scenarios/bank-alpha/compliant")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["policy_decision"]["allowed"] is True
    assert body["provider_used"] == "StubAIProvider"


def test_scenario_bank_beta_blocked() -> None:
    with TestClient(app) as client:
        response = client.get("/scenarios/bank-beta/blocked")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ["blocked", "fallback"]
    assert body["policy_decision"]["allowed"] is False


def test_scenario_bank_alpha_provider_failure() -> None:
    with TestClient(app) as client:
        response = client.get("/scenarios/bank-alpha/provider-failure")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fallback"
    assert "error" in body

    # Check that evidence was recorded for this scenario via request_id path
    request_id = body.get("request_id")
    assert request_id

    evidence_resp = client.get(f"/evidence/{request_id}")
    assert evidence_resp.status_code == 200
    evidence_body = evidence_resp.json()
    assert evidence_body["request_id"] == request_id
