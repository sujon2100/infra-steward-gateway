"""
Evidence producer for sending evidence records to the Go evidence ingester.
"""

from __future__ import annotations

import httpx

from app.config import Settings
from app.evidence.models import EvidenceRecord


class EvidenceProducer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(
            base_url=settings.evidence_ingester_uri,
            timeout=30.0,
        )

    async def send_record(self, record: EvidenceRecord) -> None:
        """
        Send an evidence record to the Go evidence ingester.

        Args:
            record: The evidence record to send.
        """
        try:
            payload = record.serializable_dict()
            response = await self.client.post(
                "/evidence/events",
                json=payload,
            )
            response.raise_for_status()
        except Exception as exc:
            # Log error but don't fail the workflow
            # In production, this might use a queue for retries
            print(f"Failed to send evidence record {record.request_id}: {exc}")

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
