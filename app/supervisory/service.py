"""
Simulated supervisory / tax reporting service.

The workflow engine dispatches each successfully enriched report to this
service after the AI provider step has completed. The implementation here
is a stub: it logs the submission, increments a Prometheus counter, and
returns a deterministic acknowledgement. A production deployment would
replace this with an HTTP client that forwards the report to an actual
supervisory or tax-reporting endpoint, behind the same interface.
"""

from __future__ import annotations

import logging
from typing import Any

from app.observability.metrics import gateway_supervisory_submissions_total
from app.workflow.request_metadata import RequestMetadata

logger = logging.getLogger(__name__)


class SupervisoryReportingService:
    def __init__(self, endpoint_label: str = "stub-supervisory-endpoint") -> None:
        self.endpoint_label = endpoint_label

    async def submit_report(
        self,
        metadata: RequestMetadata,
        enriched_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Forward an enriched report to the (simulated) supervisory service.

        Returns an acknowledgement dict the engine can include in the
        response and the evidence record.
        """
        logger.info(
            "Supervisory submission: tenant=%s scenario=%s report_id=%s endpoint=%s",
            metadata.tenant_id,
            metadata.scenario,
            metadata.report_id,
            self.endpoint_label,
        )

        gateway_supervisory_submissions_total.labels(
            tenant_id=metadata.tenant_id,
            scenario=metadata.scenario or "unknown",
            submission_status="accepted",
        ).inc()

        return {
            "endpoint": self.endpoint_label,
            "accepted": True,
            "tenant_id": metadata.tenant_id,
            "report_id": metadata.report_id,
            "payload_keys": sorted(enriched_payload.keys()),
        }
