import pytest

from app.evidence.models import EvidenceEventType
from app.evidence.service import EvidenceService


@pytest.mark.asyncio
async def test_evidence_service_lifecycle() -> None:
    svc = EvidenceService()
    record = svc.start_record(
        tenant_id="bank_alpha",
        scenario="reporting",
        report_id="r123",
        report_type="standard",
        jurisdiction="USD",
        regime="compliance",
        policy_suite_version="v1",
    )

    assert record.tenant_id == "bank_alpha"
    assert record.status == "in_progress"
    assert record.events[0].event_type == EvidenceEventType.WORKFLOW_STARTED

    record = svc.add_event(
        record,
        event_type=EvidenceEventType.POLICY_EVALUATED,
        details={"allowed": True, "reason": "ok"},
    )

    record = svc.add_event(
        record,
        event_type=EvidenceEventType.PROVIDER_SELECTED,
        details={"provider": "stub", "mode": "default"},
    )

    record = await svc.finalize(record, status="completed", decision_outcome="approved", input_hash="abc", output_hash="def")

    assert record.status == "completed"
    assert record.decision_outcome == "approved"
    assert record.input_hash == "abc"
    assert record.output_hash == "def"
    assert len(record.events) == 4
    assert record.events[-1].event_type == EvidenceEventType.WORKFLOW_COMPLETED

    got = svc.get_record(record.request_id)
    assert got is not None
    assert got.request_id == record.request_id

    list_all = svc.list_records()
    assert len(list_all) == 1

    list_filtered = svc.list_records("bank_alpha")
    assert len(list_filtered) == 1

    list_empty = svc.list_records("bank_beta")
    assert len(list_empty) == 0
