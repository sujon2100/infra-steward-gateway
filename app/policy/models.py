"""
Policy data models for InfraSteward gateway.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
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


# --- HIPAA PHI exchange models (Section 5.1.3 scenario: regional HIE
# routing PHI between hospitals, clinics, and payers). These extend the
# PolicyDecision pattern above rather than replace it; a PHI exchange is
# still a policy decision, just one that also needs consent and
# purpose-of-use as inputs.


class PHICategory(StrEnum):
    """Coarse data classification, not a full HIPAA data-element taxonomy."""

    DEMOGRAPHIC = "demographic"
    DIAGNOSIS = "diagnosis"
    MEDICATION = "medication"
    LAB_RESULT = "lab_result"
    MENTAL_HEALTH = "mental_health"
    SUBSTANCE_USE = "substance_use"
    GENETIC = "genetic"


class PurposeOfUse(StrEnum):
    """HIPAA's TPO purposes plus public health and patient-initiated access."""

    TREATMENT = "treatment"
    PAYMENT = "payment"
    HEALTHCARE_OPERATIONS = "healthcare_operations"
    PUBLIC_HEALTH = "public_health"
    RESEARCH = "research"
    PATIENT_REQUEST = "patient_request"


class OrgType(StrEnum):
    HOSPITAL = "hospital"
    CLINIC = "clinic"
    PAYER = "payer"
    RESEARCH_ORG = "research_org"


class ConsentRecord(BaseModel):
    """A patient's standing authorization for one or more HIE disclosures.

    This models the shape of a consent artifact, not a real consent
    management system — there is no revocation propagation, no versioning,
    and no link to an actual identity-proofed patient record.
    """

    consent_id: str = Field(..., min_length=1)
    patient_id: str = Field(..., min_length=1)
    granted_categories: set[PHICategory]
    granted_purposes: set[PurposeOfUse]
    authorized_recipients: set[str] = Field(default_factory=lambda: {"*"})
    expires_at: datetime | None = None
    revoked: bool = False


class PHIExchangeRequest(BaseModel):
    consent_id: str = Field(..., min_length=1)
    patient_id: str = Field(..., min_length=1)
    disclosing_org: str = Field(..., min_length=1)
    receiving_org: str = Field(..., min_length=1)
    categories: set[PHICategory] = Field(..., min_length=1)
    purpose_of_use: PurposeOfUse


class PHIExchangeDecision(PolicyDecision):
    consent_id: str | None = None
    purpose_of_use: PurposeOfUse | None = None
    phi_categories: list[PHICategory] = Field(default_factory=list)
    disclosing_org: str | None = None
    receiving_org: str | None = None
