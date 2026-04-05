"""
Policy data models for InfraSteward gateway.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

TenantId = str


class Tenant(BaseModel):
    tenant_id: TenantId = Field(..., min_length=1)
    name: str
    metadata: dict[str, Any] | None = None


class PolicyRule(BaseModel):
    id: str = Field(..., min_length=1)
    name: str
    description: str | None = None
    conditions: dict[str, Any] = Field(default_factory=dict)


class PolicyDecision(BaseModel):
    allowed: bool
    reason: str
    tenant_id: TenantId
    policies_applied: list[str] = Field(default_factory=list)
    policy_suite_version: str | None = None
    selected_provider: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
