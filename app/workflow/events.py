"""
Lightweight in-process event bus for the workflow engine.

The engine publishes named events (tenant.resolved, policy.evaluated,
provider.selected, report.enriched, supervisory.submitted,
workflow.completed, workflow.fallback) as each step completes. Subscribers
register async callbacks per event name and receive the event payload when
the engine publishes. This makes the orchestration explicitly
event-driven: the engine emits, subscribers react, and the two are
decoupled enough that new subscribers can be added without touching the
engine.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

EventPayload = dict[str, Any]
EventHandler = Callable[[EventPayload], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = {}

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._subscribers.setdefault(event_name, []).append(handler)

    def event_names(self) -> list[str]:
        return sorted(self._subscribers)

    async def publish(self, event_name: str, payload: EventPayload) -> None:
        handlers = self._subscribers.get(event_name, [])
        if not handlers:
            return
        # Run subscribers concurrently; one failing handler must not
        # block the others or break the engine.
        results = await asyncio.gather(
            *(self._safe_invoke(h, event_name, payload) for h in handlers),
            return_exceptions=False,
        )
        for r in results:
            if isinstance(r, Exception):
                logger.warning("Event handler for '%s' raised: %s", event_name, r)

    async def _safe_invoke(
        self, handler: EventHandler, event_name: str, payload: EventPayload
    ) -> Exception | None:
        try:
            await handler(payload)
            return None
        except Exception as exc:
            logger.warning("Handler error on '%s': %s", event_name, exc)
            return exc
