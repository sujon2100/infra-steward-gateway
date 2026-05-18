"""Tests for the SupervisoryReportingService stub."""

import pytest

from app.supervisory.service import SupervisoryReportingService
from app.workflow.request_metadata import RequestMetadata


def _meta(tenant: str = "bank_alpha") -> RequestMetadata:
    return RequestMetadata(
        request_id="r-1",
        tenant_id=tenant,
        scenario="reporting",
        report_id="rep-1",
        report_type="standard",
        jurisdiction="EU",
    )


@pytest.mark.asyncio
async def test_submit_report_returns_acknowledgement() -> None:
    svc = SupervisoryReportingService()
    ack = await svc.submit_report(
        _meta(),
        {"summary": "ok", "tenant_id": "bank_alpha", "result": 42},
    )

    assert ack["accepted"] is True
    assert ack["tenant_id"] == "bank_alpha"
    assert ack["report_id"] == "rep-1"
    assert ack["endpoint"] == "stub-supervisory-endpoint"
    assert ack["payload_keys"] == ["result", "summary", "tenant_id"]


@pytest.mark.asyncio
async def test_endpoint_label_is_configurable() -> None:
    svc = SupervisoryReportingService(endpoint_label="eu-supervisor-001")
    ack = await svc.submit_report(_meta(), {"x": 1})
    assert ack["endpoint"] == "eu-supervisor-001"
