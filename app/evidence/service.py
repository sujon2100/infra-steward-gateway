"""
EvidenceService implementation for Phase 2.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.evidence.models import EvidenceEvent, EvidenceEventType, EvidenceRecord
from app.evidence.producer import EvidenceProducer


class EvidenceService:
    def __init__(self, producer: EvidenceProducer | None = None) -> None:
        self._store: dict[str, EvidenceRecord] = {}
        self.producer = producer

    def start_record(
        self,
        tenant_id: str,
        scenario: str | None = None,
        report_id: str | None = None,
        report_type: str | None = None,
        jurisdiction: str | None = None,
        regime: str | None = None,
        policy_suite_version: str | None = None,
        request_id: str | None = None,
    ) -> EvidenceRecord:
        if request_id is None:
            request_id = str(uuid4())
        record = EvidenceRecord(
            request_id=request_id,
            tenant_id=tenant_id,
            scenario=scenario,
            report_id=report_id,
            report_type=report_type,
            jurisdiction=jurisdiction,
            regime=regime,
            policy_suite_version=policy_suite_version,
            status="in_progress",
        )
        record.events.append(
            EvidenceEvent(
                event_type=EvidenceEventType.WORKFLOW_STARTED,
                details={
                    "tenant_id": tenant_id,
                    "scenario": scenario,
                    "report_id": report_id,
                    "report_type": report_type,
                },
            )
        )
        self._store[request_id] = record
        return record

    def add_event(
        self,
        record: EvidenceRecord,
        event_type: EvidenceEventType,
        details: dict[str, Any],
    ) -> EvidenceRecord:
        if record.request_id not in self._store:
            raise KeyError(f"EvidenceRecord with request_id {record.request_id} not found")

        event = EvidenceEvent(event_type=event_type, details=details)
        record.events.append(event)
        self._store[record.request_id] = record
        return record

    async def finalize(
        self,
        record: EvidenceRecord,
        status: str,
        decision_outcome: str | None = None,
        input_hash: str | None = None,
        output_hash: str | None = None,
        provider_name: str | None = None,
        provider_mode: str | None = None,
    ) -> EvidenceRecord:
        if record.request_id not in self._store:
            raise KeyError(f"EvidenceRecord with request_id {record.request_id} not found")

        record.status = status
        record.decision_outcome = decision_outcome
        record.input_hash = input_hash
        record.output_hash = output_hash
        if provider_name is not None:
            record.provider_name = provider_name
        if provider_mode is not None:
            record.provider_mode = provider_mode

        record.events.append(
            EvidenceEvent(
                event_type=EvidenceEventType.WORKFLOW_COMPLETED,
                details={
                    "status": status,
                    "decision_outcome": decision_outcome,
                    "input_hash": input_hash,
                    "output_hash": output_hash,
                },
            )
        )

        self._store[record.request_id] = record

        # Send to evidence ingester if producer is configured
        if self.producer:
            await self.producer.send_record(record)

        return record

    def get_record(self, request_id: str) -> EvidenceRecord | None:
        return self._store.get(request_id)

    def list_records(self, tenant_id: str | None = None) -> list[EvidenceRecord]:
        if tenant_id is None:
            return list(self._store.values())
        return [rec for rec in self._store.values() if rec.tenant_id == tenant_id]
