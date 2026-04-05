"""
Request metadata model for gateway workflow orchestration.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RequestMetadata(BaseModel):
    request_id: str
    tenant_id: str
    scenario: str | None = None
    report_id: str | None = None
    report_type: str | None = None
    jurisdiction: str | None = None
    regime: str | None = None
    user_id: str | None = None

    class Config:
        orm_mode = True


class ReportRequest(BaseModel):
    tenant_id: str
    scenario: str | None = None
    report_id: str | None = None
    report_type: str | None = None
    jurisdiction: str | None = None
    regime: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    class Config:
        orm_mode = True
