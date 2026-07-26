"""
Second stub AI provider, used to demonstrate per-tenant provider selection.

Returns a structurally similar but distinguishable enrichment payload, so
evidence records and metrics can show which provider handled a request.
"""

from __future__ import annotations

from typing import Any

from app.providers.base import AbstractAIProvider
from app.providers.enrichment_class import EnrichmentClass, FallbackStrategy
from app.workflow.request_metadata import RequestMetadata


class StubAIProviderB(AbstractAIProvider):
    # Class 1 (NARRATIVE) with drop-and-signal fallback, same shape as
    # StubAIProvider. Kept as a distinct class so the routing decision
    # is observable in evidence.
    enrichment_class = EnrichmentClass.NARRATIVE
    fallback_strategy = FallbackStrategy.DROP_AND_SIGNAL

    async def generate_enrichment(
        self,
        metadata: RequestMetadata,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if metadata.scenario == "provider_failure" or payload.get("provider_failure"):
            raise RuntimeError("Simulated provider failure (provider B)")

        summary = f"Stub-B enrichment for tenant {metadata.tenant_id}"
        if metadata.scenario:
            summary += f", scenario {metadata.scenario}"

        return {
            "enrichment": "stubbed_b",
            "tenant_id": metadata.tenant_id,
            "scenario": metadata.scenario,
            "report_id": metadata.report_id,
            "provider_variant": "B",
            "result": {
                "summary": summary,
                "payload_size": len(str(payload)),
            },
        }
