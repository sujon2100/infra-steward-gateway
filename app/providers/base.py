"""
AI provider abstraction for InfraSteward gateway.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.workflow.request_metadata import RequestMetadata


class AbstractAIProvider(Protocol):
    async def generate_enrichment(
        self,
        metadata: RequestMetadata,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate an enrichment payload for a report."""
        ...
