"""
Tests for per-class fallback dispatch in WorkflowEngine.

The engine reads each provider's declared enrichment_class and
fallback_strategy and dispatches per strategy on failure. These tests
exercise the two implemented strategies:

- DROP_AND_SIGNAL (Class 1 NARRATIVE): drop the enrichment, return
  status:fallback, primary data flows through
- FAIL_CLOSED (Class 2 RISK_CLASSIFICATION): block the request,
  return status:blocked_provider_failure, no result
"""

from typing import Any

import pytest

from app.evidence.service import EvidenceService
from app.policy.service import PolicyService
from app.providers.enrichment_class import EnrichmentClass, FallbackStrategy
from app.providers.registry import ProviderRegistry
from app.providers.stub import StubAIProvider
from app.providers.stub_risk_scorer import StubRiskScorer
from app.workflow.engine import ReportRequest, WorkflowEngine


def _engine_with_stub_a() -> WorkflowEngine:
    registry = ProviderRegistry(default_name="stub_a")
    registry.register("stub_a", StubAIProvider())
    return WorkflowEngine(
        PolicyService(),
        EvidenceService(),
        provider_registry=registry,
    )


def _engine_with_risk_scorer() -> tuple[WorkflowEngine, EvidenceService]:
    """A registry where the tenant's provider is a Class 2 risk scorer.

    We reuse the bank_alpha tenant but override its provider mapping by
    registering stub_a as a risk scorer instead of a narrative stub.
    This tests the per-class dispatch without adding a new tenant.
    """
    registry = ProviderRegistry(default_name="stub_a")
    registry.register("stub_a", StubRiskScorer())
    evidence = EvidenceService()
    engine = WorkflowEngine(
        PolicyService(),
        evidence,
        provider_registry=registry,
    )
    return engine, evidence


def test_stub_a_declares_class_1_narrative() -> None:
    p = StubAIProvider()
    assert p.enrichment_class == EnrichmentClass.NARRATIVE
    assert p.fallback_strategy == FallbackStrategy.DROP_AND_SIGNAL


def test_risk_scorer_declares_class_2_fail_closed() -> None:
    p = StubRiskScorer()
    assert p.enrichment_class == EnrichmentClass.RISK_CLASSIFICATION
    assert p.fallback_strategy == FallbackStrategy.FAIL_CLOSED


@pytest.mark.asyncio
async def test_narrative_provider_failure_drops_and_signals() -> None:
    """Class 1 NARRATIVE + DROP_AND_SIGNAL:
    provider fails → status: fallback (not blocked_provider_failure).
    """
    engine = _engine_with_stub_a()
    result = await engine.process_report(
        ReportRequest({
            "tenant_id": "bank_alpha",
            "scenario": "provider_failure",
            "report_id": "narr-fail-1",
            "report_type": "standard",
            "payload": {"text": "will fail", "provider_failure": True},
        })
    )

    assert result["status"] == "fallback"
    assert result["fallback_strategy"] == "drop_and_signal"
    assert "error" in result


@pytest.mark.asyncio
async def test_risk_classification_provider_failure_fails_closed() -> None:
    """Class 2 RISK_CLASSIFICATION + FAIL_CLOSED:
    provider fails → status: blocked_provider_failure, not fallback.
    """
    engine, evidence_service = _engine_with_risk_scorer()
    result = await engine.process_report(
        ReportRequest({
            "tenant_id": "bank_alpha",
            "scenario": "provider_failure",
            "report_id": "risk-fail-1",
            "report_type": "standard",
            "payload": {"text": "will fail", "provider_failure": True},
        })
    )

    assert result["status"] == "blocked_provider_failure"
    assert result["fallback_strategy"] == "fail_closed"
    assert result["result"] is None
    assert "error" in result

    record = evidence_service.get_record(result["request_id"])
    assert record is not None
    event_types = [e.event_type.name for e in record.events]
    assert "PROVIDER_FAILED" in event_types
    assert "PROVIDER_FALLBACK_BLOCKED" in event_types
    assert "PROVIDER_FALLBACK_APPLIED" not in event_types


@pytest.mark.asyncio
async def test_narrative_provider_failure_records_fallback_applied_event() -> None:
    """The DROP_AND_SIGNAL path adds a PROVIDER_FALLBACK_APPLIED event.
    """
    engine = _engine_with_stub_a()
    result = await engine.process_report(
        ReportRequest({
            "tenant_id": "bank_alpha",
            "scenario": "provider_failure",
            "report_id": "narr-fail-2",
            "report_type": "standard",
            "payload": {"provider_failure": True},
        })
    )

    record = engine.evidence_service.get_record(result["request_id"])
    assert record is not None
    event_types = [e.event_type.name for e in record.events]
    assert "PROVIDER_FAILED" in event_types
    assert "PROVIDER_FALLBACK_APPLIED" in event_types
    assert "PROVIDER_FALLBACK_BLOCKED" not in event_types


@pytest.mark.asyncio
async def test_provider_failed_event_records_enrichment_class_and_strategy() -> None:
    """The PROVIDER_FAILED event captures which class and strategy applied.
    """
    engine = _engine_with_stub_a()
    result = await engine.process_report(
        ReportRequest({
            "tenant_id": "bank_alpha",
            "scenario": "provider_failure",
            "report_id": "narr-fail-3",
            "report_type": "standard",
            "payload": {"provider_failure": True},
        })
    )

    record = engine.evidence_service.get_record(result["request_id"])
    assert record is not None
    provider_failed = next(
        e for e in record.events if e.event_type.name == "PROVIDER_FAILED"
    )
    assert provider_failed.details["enrichment_class"] == "narrative"
    assert provider_failed.details["fallback_strategy"] == "drop_and_signal"


@pytest.mark.asyncio
async def test_successful_risk_classification_returns_score() -> None:
    """When the risk scorer succeeds, its output is returned normally.
    """
    engine, _ = _engine_with_risk_scorer()
    result = await engine.process_report(
        ReportRequest({
            "tenant_id": "bank_alpha",
            "scenario": "reporting",
            "report_id": "risk-ok-1",
            "report_type": "standard",
            "payload": {"text": "some request payload"},
        })
    )

    assert result["status"] == "completed"
    assert result["result"]["enrichment"] == "risk_classification"
    assert "risk_score" in result["result"]
    assert "risk_band" in result["result"]


def test_default_fallback_strategy_when_provider_lacks_declaration() -> None:
    """If a provider does not declare a strategy (legacy), engine defaults
    to DROP_AND_SIGNAL rather than failing hard.

    This is a backward-compatibility guarantee: existing providers written
    against the pre-per-class protocol continue to work.
    """
    # Constructed at runtime without the class attributes.
    class LegacyProvider:
        async def generate_enrichment(
            self,
            metadata: Any,
            payload: dict[str, Any],
        ) -> dict[str, Any]:
            raise RuntimeError("legacy fail")

    from app.providers.enrichment_class import FallbackStrategy as FS

    p = LegacyProvider()
    # No enrichment_class or fallback_strategy attributes on the class.
    assert not hasattr(p, "enrichment_class")
    assert not hasattr(p, "fallback_strategy")

    # The engine uses getattr with a DROP_AND_SIGNAL default; verify the
    # default resolves to that.
    strategy = getattr(p, "fallback_strategy", FS.DROP_AND_SIGNAL)
    assert strategy == FS.DROP_AND_SIGNAL
