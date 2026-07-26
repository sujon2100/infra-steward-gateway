"""
Evidence domain models for InfraSteward gateway.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from typing import Any, cast

from pydantic import BaseModel, Field


class EvidenceEventType(StrEnum):
    WORKFLOW_STARTED = "WORKFLOW_STARTED"
    POLICY_EVALUATED = "POLICY_EVALUATED"
    PROVIDER_SELECTED = "PROVIDER_SELECTED"
    PROVIDER_FAILED = "PROVIDER_FAILED"
    # Per-class fallback outcomes: what the engine did after PROVIDER_FAILED,
    # dispatched from the failed provider's declared fallback strategy.
    PROVIDER_FALLBACK_APPLIED = "PROVIDER_FALLBACK_APPLIED"
    PROVIDER_FALLBACK_BLOCKED = "PROVIDER_FALLBACK_BLOCKED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"


class EvidenceEvent(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: EvidenceEventType
    details: dict[str, Any] = Field(default_factory=dict)


class EvidenceRecord(BaseModel):
    request_id: str
    tenant_id: str
    scenario: str | None = None
    report_id: str | None = None
    report_type: str | None = None
    jurisdiction: str | None = None
    regime: str | None = None
    policy_suite_version: str | None = None
    policies_applied: list[str] = Field(default_factory=list)
    decision_outcome: str | None = None
    provider_name: str | None = None
    provider_mode: str | None = None
    redaction_applied: bool | None = None
    risk_level: str | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    events: list[EvidenceEvent] = Field(default_factory=list)
    status: str = "in_progress"

    class Config:
        frozen = False
        orm_mode = True

    def serializable_dict(self) -> dict[str, Any]:
        """Return JSON-safe dict for HTTP transmission (datetime -> ISO strings)."""
        # Pydantic JSON encoder handles datetime conversion correctly.
        return cast(dict[str, Any], json.loads(self.json()))
