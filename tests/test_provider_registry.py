"""
Tests for ProviderRegistry and per-tenant provider selection.
"""

import pytest

from app.evidence.service import EvidenceService
from app.policy.service import PolicyService
from app.providers.registry import ProviderNotRegisteredError, ProviderRegistry
from app.providers.stub import StubAIProvider
from app.providers.stub_b import StubAIProviderB
from app.workflow.engine import ReportRequest, WorkflowEngine


def _build_engine() -> tuple[WorkflowEngine, EvidenceService]:
    policy_service = PolicyService()
    evidence_service = EvidenceService()
    registry = ProviderRegistry(default_name="stub_a")
    registry.register("stub_a", StubAIProvider())
    registry.register("stub_b", StubAIProviderB())
    engine = WorkflowEngine(
        policy_service,
        evidence_service,
        provider_registry=registry,
    )
    return engine, evidence_service


def test_registry_register_and_get() -> None:
    registry = ProviderRegistry()
    stub_a = StubAIProvider()
    stub_b = StubAIProviderB()
    registry.register("stub_a", stub_a)
    registry.register("stub_b", stub_b)

    assert registry.names() == ["stub_a", "stub_b"]
    assert registry.get("stub_a") is stub_a
    assert registry.get("stub_b") is stub_b


def test_registry_default_name_returned_when_none_requested() -> None:
    registry = ProviderRegistry()
    stub_a = StubAIProvider()
    registry.register("stub_a", stub_a)

    assert registry.default_name == "stub_a"
    assert registry.get(None) is stub_a


def test_registry_unknown_provider_raises() -> None:
    registry = ProviderRegistry()
    registry.register("stub_a", StubAIProvider())

    with pytest.raises(ProviderNotRegisteredError):
        registry.get("stub_z")


def test_policy_service_selects_provider_per_tenant() -> None:
    service = PolicyService()

    alpha = service.evaluate(tenant_id="bank_alpha", scenario="reporting")
    beta_allowed = service.evaluate(tenant_id="bank_beta", scenario="analysis")
    beta_denied = service.evaluate(tenant_id="bank_beta", scenario="reporting")
    mars = service.evaluate(tenant_id="bank_mars", scenario="reporting")
    neptune = service.evaluate(tenant_id="bank_neptune", scenario="reporting")

    assert alpha.selected_provider == "stub_a"
    assert beta_allowed.selected_provider == "stub_b"
    assert beta_denied.selected_provider is None
    assert mars.selected_provider == "stub_a"
    assert neptune.selected_provider == "stub_b"


@pytest.mark.asyncio
async def test_workflow_engine_uses_stub_a_for_bank_alpha() -> None:
    engine, evidence_service = _build_engine()

    result = await engine.process_report(
        ReportRequest({
            "tenant_id": "bank_alpha",
            "scenario": "reporting",
            "report_id": "alpha-1",
            "report_type": "standard",
            "payload": {"text": "hello"},
        })
    )

    assert result["status"] == "completed"
    assert result["provider_used"] == "StubAIProvider"
    assert result["result"]["enrichment"] == "stubbed"

    record = evidence_service.get_record(result["request_id"])
    assert record is not None
    provider_event = next(e for e in record.events if e.event_type.name == "PROVIDER_SELECTED")
    assert provider_event.details["provider_name"] == "stub_a"


@pytest.mark.asyncio
async def test_workflow_engine_uses_stub_b_for_bank_mars_via_neptune() -> None:
    # bank_neptune maps to stub_b in the PolicyService map; the engine should
    # invoke StubAIProviderB rather than the default StubAIProvider.
    engine, evidence_service = _build_engine()

    result = await engine.process_report(
        ReportRequest({
            "tenant_id": "bank_neptune",
            "scenario": "reporting",
            "report_id": "nep-1",
            "report_type": "standard",
            "payload": {"text": "hi"},
        })
    )

    assert result["status"] == "completed"
    assert result["provider_used"] == "StubAIProviderB"
    assert result["result"]["enrichment"] == "stubbed_b"
    assert result["result"]["provider_variant"] == "B"

    record = evidence_service.get_record(result["request_id"])
    assert record is not None
    provider_event = next(e for e in record.events if e.event_type.name == "PROVIDER_SELECTED")
    assert provider_event.details["provider_name"] == "stub_b"
