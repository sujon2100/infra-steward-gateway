import pytest

from app.evidence.models import EvidenceEventType
from app.evidence.service import EvidenceService
from app.policy.models import ConsentRecord, PHIExchangeRequest
from app.policy.service import PolicyService
from app.workflow.phi_exchange import PHIExchangeCoordinator


@pytest.mark.asyncio
async def test_evidence_captures_consent_basis_for_allowed_exchange() -> None:
    policy_service = PolicyService()
    policy_service.register_consent(
        ConsentRecord(
            consent_id="c1",
            patient_id="p1",
            granted_categories={"diagnosis"},
            granted_purposes={"treatment"},
            authorized_recipients={"hie_hospital_north"},
        )
    )
    evidence_service = EvidenceService()
    coordinator = PHIExchangeCoordinator(policy_service, evidence_service)

    result = await coordinator.process(
        PHIExchangeRequest(
            consent_id="c1",
            patient_id="p1",
            disclosing_org="hie_clinic_riverside",
            receiving_org="hie_hospital_north",
            categories={"diagnosis"},
            purpose_of_use="treatment",
        )
    )

    record = evidence_service.get_record(result["request_id"])
    assert record is not None
    assert record.status == "completed"
    assert record.decision_outcome == "approved"
    assert record.consent_id == "c1"
    assert record.purpose_of_use == "treatment"
    assert record.phi_categories == ["diagnosis"]
    assert record.disclosing_org == "hie_clinic_riverside"
    assert record.receiving_org == "hie_hospital_north"

    event_types = [event.event_type for event in record.events]
    assert EvidenceEventType.CONSENT_EVALUATED in event_types


@pytest.mark.asyncio
async def test_evidence_captures_consent_basis_for_denied_exchange() -> None:
    policy_service = PolicyService()
    evidence_service = EvidenceService()
    coordinator = PHIExchangeCoordinator(policy_service, evidence_service)

    result = await coordinator.process(
        PHIExchangeRequest(
            consent_id="no-such-consent",
            patient_id="p1",
            disclosing_org="hie_clinic_riverside",
            receiving_org="hie_hospital_north",
            categories={"diagnosis"},
            purpose_of_use="treatment",
        )
    )

    record = evidence_service.get_record(result["request_id"])
    assert record is not None
    assert record.status == "blocked"
    assert record.decision_outcome == "denied"
    assert record.consent_id == "no-such-consent"
