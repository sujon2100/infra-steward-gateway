"""
Stub Class 2 (RISK_CLASSIFICATION) provider with FAIL_CLOSED strategy.

This provider illustrates the per-class fallback contract: unlike the
narrative stubs, a risk-classification provider cannot silently drop
its output on failure, because the score is what the caller uses to
decide. When this provider raises, the workflow engine blocks the
request rather than returning a partial response.
"""

from __future__ import annotations

from typing import Any

from app.providers.base import AbstractAIProvider
from app.providers.enrichment_class import EnrichmentClass, FallbackStrategy
from app.workflow.request_metadata import RequestMetadata


class StubRiskScorer(AbstractAIProvider):
    enrichment_class = EnrichmentClass.RISK_CLASSIFICATION
    fallback_strategy = FallbackStrategy.FAIL_CLOSED

    async def generate_enrichment(
        self,
        metadata: RequestMetadata,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if metadata.scenario == "provider_failure" or payload.get("provider_failure"):
            raise RuntimeError("Simulated risk scorer failure")

        payload_size = len(str(payload))
        risk_score = min(payload_size % 100, 99)
        risk_band = "low" if risk_score < 33 else ("medium" if risk_score < 67 else "high")

        return {
            "enrichment": "risk_classification",
            "tenant_id": metadata.tenant_id,
            "scenario": metadata.scenario,
            "report_id": metadata.report_id,
            "risk_score": risk_score,
            "risk_band": risk_band,
        }
