"""
Tenant context data models.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TenantContext(BaseModel):
    """Resolved tenant context propagated through the request lifecycle.

    Holds the canonical tenant identifier, a display name, the named policy
    scope to evaluate against, and the tenant's home jurisdiction. Created
    once per request by TenantContextManager and read by downstream steps.
    """

    tenant_id: str = Field(..., min_length=1)
    display_name: str
    policy_scope: str
    jurisdiction: str
