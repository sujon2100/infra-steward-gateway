import pytest

from app.evidence.models import EvidenceEventType
from app.evidence.service import EvidenceService
from app.policy.dsi_models import DSIAdvisoryRequest, DSISourceAttributes
from app.policy.service import PolicyService
from app.providers.registry import ProviderRegistry
from app.providers.stub import StubAIProvider
from app.workflow.dsi_advisory import DSIAdvisoryCoordinator


def _registry() -> ProviderRegistry:
    registry = ProviderRegistry(default_name="stub_a")
    registry.register("stub_a", StubAIProvider())
    return registry


@pytest.mark.asyncio
async def test_evidence_captures_transparency_basis_and_runs_provider_when_allowed() -> None:
    policy_service = PolicyService()
    policy_service.register_dsi(
        DSISourceAttributes(
            dsi_id="d1",
            model_name="TestScorer",
            developer_name="Acme Health",
            developer_contact="dev@acme.example",
            funding_source="internal",
            output_value_description="risk score",
            output_type="prediction",
            intended_use="flag high risk patients",
            intended_patient_population="adult inpatients",
            intended_users=["physician"],
            decision_making_role="informs",
            cautioned_out_of_scope_uses=["pediatric patients"],
            known_risks_and_limitations="lower sensitivity in edge cases",
        )
    )
    evidence_service = EvidenceService()
    coordinator = DSIAdvisoryCoordinator(policy_service, evidence_service, _registry())

    result = await coordinator.process(
        DSIAdvisoryRequest(dsi_id="d1", requesting_org="hie_hospital_north", encounter_id="enc-1")
    )

    record = evidence_service.get_record(result["request_id"])
    assert record is not None
    assert record.status == "completed"
    assert record.decision_outcome == "approved"
    assert record.dsi_id == "d1"
    assert record.dsi_output_type == "prediction"
    assert record.dsi_decision_making_role == "informs"
    assert record.dsi_missing_attributes == []
    assert result["advisory_output"] is not None

    event_types = [event.event_type for event in record.events]
    assert EvidenceEventType.DSI_TRANSPARENCY_EVALUATED in event_types
    assert EvidenceEventType.PROVIDER_SELECTED in event_types


@pytest.mark.asyncio
async def test_evidence_blocks_before_invoking_provider_when_attributes_missing() -> None:
    policy_service = PolicyService()
    policy_service.register_dsi(
        DSISourceAttributes(dsi_id="incomplete", model_name="IncompleteModel")
    )
    evidence_service = EvidenceService()
    coordinator = DSIAdvisoryCoordinator(policy_service, evidence_service, _registry())

    result = await coordinator.process(
        DSIAdvisoryRequest(
            dsi_id="incomplete", requesting_org="hie_hospital_north", encounter_id="enc-2"
        )
    )

    record = evidence_service.get_record(result["request_id"])
    assert record is not None
    assert record.status == "blocked"
    assert record.decision_outcome == "denied"
    assert record.dsi_missing_attributes != []
    assert result["advisory_output"] is None

    event_types = [event.event_type for event in record.events]
    assert EvidenceEventType.PROVIDER_SELECTED not in event_types
