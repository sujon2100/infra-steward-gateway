"""
Stub AI provider implementation for Phase 3.
"""

from __future__ import annotations

from typing import Any

from app.providers.base import AbstractAIProvider
from app.providers.enrichment_class import EnrichmentClass, FallbackStrategy
from app.workflow.request_metadata import RequestMetadata


class StubAIProvider(AbstractAIProvider):
    # Class 1 (NARRATIVE): the stub returns a supplementary `summary`
    # string alongside the input payload. Primary data is untouched,
    # so dropping the enrichment on failure leaves the caller with the
    # primary data and a status:fallback signal.
    enrichment_class = EnrichmentClass.NARRATIVE
    fallback_strategy = FallbackStrategy.DROP_AND_SIGNAL

    async def generate_enrichment(
        self,
        metadata: RequestMetadata,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        # Simulate a provider failure scenario.
        if metadata.scenario == "provider_failure" or payload.get("provider_failure"):
            raise RuntimeError("Simulated provider failure")

        # Deterministic stub enrichment response.
        summary = f"Stub enrichment for tenant {metadata.tenant_id}"
        if metadata.scenario:
            summary += f", scenario {metadata.scenario}"

        return {
            "enrichment": "stubbed",
            "tenant_id": metadata.tenant_id,
            "scenario": metadata.scenario,
            "report_id": metadata.report_id,
            "result": {
                "summary": summary,
                "payload_size": len(str(payload)),
            },
        }
