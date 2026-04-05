"""
Unit tests for WorkflowEngine behavior.
"""

import pytest

from app.evidence.service import EvidenceService
from app.policy.service import PolicyService
from app.providers.stub import StubAIProvider
from app.workflow.engine import ReportRequest, WorkflowEngine


@pytest.mark.asyncio
async def test_workflow_engine_bank_alpha_process_report() -> None:
    policy_service = PolicyService()
    evidence_service = EvidenceService()
    ai_provider = StubAIProvider()
    engine = WorkflowEngine(policy_service, evidence_service, ai_provider)

    request = ReportRequest({
        "tenant_id": "bank_alpha",
        "scenario": "reporting",
        "report_id": "r4",
        "report_type": "standard",
        "payload": {"text": "hello"},
    })

    result = await engine.process_report(request)

    assert result["status"] == "completed"
    assert result["policy_decision"]["allowed"] is True
    assert result["provider_used"] == "StubAIProvider"

    record = evidence_service.get_record(result["request_id"])
    assert record is not None
    assert record.status == "completed"
    assert any(event.event_type.name == "WORKFLOW_STARTED" for event in record.events)
    assert any(event.event_type.name == "WORKFLOW_COMPLETED" for event in record.events)
