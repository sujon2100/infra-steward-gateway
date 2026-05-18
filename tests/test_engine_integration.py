"""
End-to-end engine tests for the diagram-aligned components:
TenantContextManager, jurisdiction-aware policy, SupervisoryReportingService,
and the EventBus working together inside WorkflowEngine.
"""

from typing import Any

import pytest

from app.evidence.service import EvidenceService
from app.policy.service import PolicyService
from app.providers.registry import ProviderRegistry
from app.providers.stub import StubAIProvider
from app.providers.stub_b import StubAIProviderB
from app.supervisory.service import SupervisoryReportingService
from app.tenants.context_manager import TenantContextManager
from app.workflow.engine import ReportRequest, WorkflowEngine
from app.workflow.events import EventBus, EventHandler


def _engine() -> tuple[WorkflowEngine, EventBus, list[tuple[str, dict[str, Any]]]]:
    registry = ProviderRegistry(default_name="stub_a")
    registry.register("stub_a", StubAIProvider())
    registry.register("stub_b", StubAIProviderB())

    bus = EventBus()
    seen: list[tuple[str, dict[str, Any]]] = []

    async def recorder(name: str, payload: dict[str, Any]) -> None:
        seen.append((name, payload))

    def make_handler(event_name: str) -> EventHandler:
        async def handler(payload: dict[str, Any]) -> None:
            await recorder(event_name, payload)
        return handler

    for event in [
        "tenant.resolved",
        "policy.evaluated",
        "provider.selected",
        "supervisory.submitted",
        "workflow.completed",
        "workflow.fallback",
    ]:
        bus.subscribe(event, make_handler(event))

    engine = WorkflowEngine(
        PolicyService(),
        EvidenceService(),
        provider_registry=registry,
        tenant_context_manager=TenantContextManager(),
        supervisory_service=SupervisoryReportingService(endpoint_label="test-endpoint"),
        event_bus=bus,
    )
    return engine, bus, seen


@pytest.mark.asyncio
async def test_compliant_request_emits_full_event_sequence_and_supervisory_ack() -> None:
    engine, _bus, seen = _engine()

    result = await engine.process_report(
        ReportRequest({
            "tenant_id": "bank_alpha",
            "scenario": "reporting",
            "report_id": "evt-1",
            "report_type": "standard",
            "payload": {"text": "hello"},
        })
    )

    assert result["status"] == "completed"
    assert result["provider_used"] == "StubAIProvider"
    assert result["supervisory_submission"]["accepted"] is True
    assert result["supervisory_submission"]["endpoint"] == "test-endpoint"

    event_names = [name for name, _ in seen]
    # All five lifecycle events fire in order for a compliant flow.
    assert event_names == [
        "tenant.resolved",
        "policy.evaluated",
        "provider.selected",
        "supervisory.submitted",
        "workflow.completed",
    ]


@pytest.mark.asyncio
async def test_denied_request_skips_provider_and_supervisory_events() -> None:
    engine, _bus, seen = _engine()

    result = await engine.process_report(
        ReportRequest({
            "tenant_id": "bank_beta",
            "scenario": "reporting",
            "report_id": "evt-2",
            "report_type": "standard",
            "payload": {"text": "blocked"},
        })
    )

    assert result["status"] == "blocked"
    assert "supervisory_submission" not in result

    event_names = [name for name, _ in seen]
    assert event_names == ["tenant.resolved", "policy.evaluated", "workflow.completed"]


@pytest.mark.asyncio
async def test_provider_failure_emits_fallback_event_not_supervisory() -> None:
    engine, _bus, seen = _engine()

    result = await engine.process_report(
        ReportRequest({
            "tenant_id": "bank_alpha",
            "scenario": "provider_failure",
            "report_id": "evt-3",
            "report_type": "standard",
            "payload": {"text": "fail", "provider_failure": True},
        })
    )

    assert result["status"] == "fallback"
    event_names = [name for name, _ in seen]
    # Provider was selected and then failed; no supervisory submission.
    assert "provider.selected" in event_names
    assert "supervisory.submitted" not in event_names
    assert "workflow.fallback" in event_names


@pytest.mark.asyncio
async def test_jurisdiction_mismatch_is_denied_by_policy() -> None:
    engine, _bus, seen = _engine()

    # bank_alpha is registered in EU; an explicit US jurisdiction must
    # be rejected by the jurisdiction policy check.
    result = await engine.process_report(
        ReportRequest({
            "tenant_id": "bank_alpha",
            "scenario": "reporting",
            "report_id": "evt-4",
            "report_type": "standard",
            "jurisdiction": "US",
            "payload": {"text": "wrong region"},
        })
    )

    assert result["status"] == "blocked"
    assert result["policy_decision"]["allowed"] is False
    assert "jurisdiction" in result["policy_decision"]["reason"].lower()
    assert "jurisdiction_policy" in result["policy_decision"]["policies_applied"]
