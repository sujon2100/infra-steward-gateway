"""
Unit tests for health and info endpoints.

Tests the basic health check and info endpoints exposed by the gateway.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client fixture."""
    return TestClient(app)


@pytest.mark.unit
def test_health_endpoint_returns_200(client: TestClient) -> None:
    """Test that /health endpoint returns 200 OK with healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.unit
def test_health_endpoint_has_version(client: TestClient) -> None:
    """Test that /health endpoint includes version info."""
    response = client.get("/health")
    body = response.json()
    assert "version" in body
    assert body["version"] == "0.1.0"


@pytest.mark.unit
def test_health_endpoint_has_uptime(client: TestClient) -> None:
    """Test that /health endpoint includes uptime."""
    response = client.get("/health")
    body = response.json()
    assert "uptime_seconds" in body
    assert body["uptime_seconds"] >= 0


@pytest.mark.unit
def test_info_endpoint_returns_200(client: TestClient) -> None:
    """Test that /info endpoint returns 200 OK."""
    response = client.get("/info")
    assert response.status_code == 200


@pytest.mark.unit
def test_info_endpoint_includes_service_name(client: TestClient) -> None:
    """Test that /info endpoint includes service name."""
    response = client.get("/info")
    body = response.json()
    assert "service" in body
    assert body["service"] == "InfraSteward Gateway"


@pytest.mark.unit
def test_info_endpoint_includes_environment(client: TestClient) -> None:
    """Test that /info endpoint includes environment."""
    response = client.get("/info")
    body = response.json()
    assert "environment" in body


@pytest.mark.unit
def test_metrics_endpoint_returns_200(client: TestClient) -> None:
    """Test that /metrics endpoint returns 200 OK."""
    response = client.get("/metrics")
    assert response.status_code == 200


@pytest.mark.unit
def test_metrics_endpoint_returns_prometheus_format(client: TestClient) -> None:
    """Test that /metrics endpoint returns Prometheus-format metrics."""
    response = client.get("/metrics")
    content = response.text
    assert "HELP" in content or "TYPE" in content or "gateway_" in content
    assert "gateway_policy_outcomes_total" in content
    assert "gateway_provider_outcomes_total" in content
    assert response.headers["content-type"] == "text/plain; charset=utf-8"


@pytest.mark.unit
def test_root_endpoint_returns_200(client: TestClient) -> None:
    """Test that / endpoint returns 200 OK."""
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert "service" in body
    assert "endpoints" in body
