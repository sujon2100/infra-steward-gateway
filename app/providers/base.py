"""
AI provider abstraction for InfraSteward gateway.

Every concrete provider must declare which class of AI enrichment it
performs and which fallback strategy the workflow engine should apply
on failure. See app/providers/enrichment_class.py for the taxonomy.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.providers.enrichment_class import EnrichmentClass, FallbackStrategy
from app.workflow.request_metadata import RequestMetadata


@runtime_checkable
class AbstractAIProvider(Protocol):
    """Interface implemented by every AI provider (stub or real).

    A provider declares its enrichment class and fallback strategy as
    class attributes so the workflow engine can dispatch per-class
    fallback behaviour without having to know the concrete provider
    type.
    """

    enrichment_class: EnrichmentClass
    fallback_strategy: FallbackStrategy

    async def generate_enrichment(
        self,
        metadata: RequestMetadata,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate an enrichment payload for a report."""
        ...
