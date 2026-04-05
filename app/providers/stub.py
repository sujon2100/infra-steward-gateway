"""
Stub AI provider implementation for Phase 3.
"""

from __future__ import annotations

from typing import Any

from app.providers.base import AbstractAIProvider
from app.workflow.request_metadata import RequestMetadata


class StubAIProvider(AbstractAIProvider):
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
