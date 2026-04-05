import asyncio
from typing import Any, cast

import httpx

from app.config import Settings
from app.evidence.models import EvidenceEvent, EvidenceEventType, EvidenceRecord
from app.evidence.producer import EvidenceProducer


def test_evidence_record_serializable_dict_datetime_to_iso() -> None:
    record = EvidenceRecord(request_id="test-1", tenant_id="tenant-1")
    record.events.append(
        EvidenceEvent(
            event_type=EvidenceEventType.WORKFLOW_STARTED,
            details={"initial": True},
        )
    )

    payload = record.serializable_dict()

    assert "events" in payload
    assert isinstance(payload["events"], list)

    ts = payload["events"][0]["timestamp"]
    assert isinstance(ts, str)
    assert "T" in ts


def test_evidence_producer_send_record_uses_serializable_dict() -> None:
    record = EvidenceRecord(request_id="test-2", tenant_id="tenant-2")

    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

    class DummyClient:
        async def post(self, url: str, json: dict[str, Any]) -> "DummyResponse":
            assert url == "/evidence/events"
            assert isinstance(json, dict)
            # Should serialize datetime on events (even if empty event list, this checks type)
            return DummyResponse()

    settings = Settings(evidence_ingester_uri="http://localhost:8081")
    producer = EvidenceProducer(settings)
    producer.client = cast(httpx.AsyncClient, DummyClient())

    # verify no exception is raised
    asyncio.run(producer.send_record(record))
