"""Tests for the in-process EventBus."""

from typing import Any

import pytest

from app.workflow.events import EventBus


@pytest.mark.asyncio
async def test_publish_invokes_subscribed_handler() -> None:
    bus = EventBus()
    received: list[dict[str, Any]] = []

    async def handler(payload: dict[str, Any]) -> None:
        received.append(payload)

    bus.subscribe("policy.evaluated", handler)
    await bus.publish("policy.evaluated", {"allowed": True})

    assert received == [{"allowed": True}]


@pytest.mark.asyncio
async def test_publish_with_no_subscribers_does_nothing() -> None:
    bus = EventBus()
    # Should not raise.
    await bus.publish("nothing.subscribed", {"x": 1})


@pytest.mark.asyncio
async def test_multiple_subscribers_all_receive_event() -> None:
    bus = EventBus()
    a: list[int] = []
    b: list[int] = []

    async def ha(p: dict[str, Any]) -> None:
        a.append(p["v"])

    async def hb(p: dict[str, Any]) -> None:
        b.append(p["v"])

    bus.subscribe("e", ha)
    bus.subscribe("e", hb)
    await bus.publish("e", {"v": 7})

    assert a == [7] and b == [7]


@pytest.mark.asyncio
async def test_failing_handler_does_not_block_others() -> None:
    bus = EventBus()
    received: list[str] = []

    async def good(_: dict[str, Any]) -> None:
        received.append("good")

    async def bad(_: dict[str, Any]) -> None:
        raise RuntimeError("kaboom")

    bus.subscribe("e", bad)
    bus.subscribe("e", good)
    # Must not raise: the bus swallows handler errors and logs them.
    await bus.publish("e", {})

    assert "good" in received


def test_event_names_lists_subscribed_event_keys() -> None:
    bus = EventBus()

    async def h(_: dict[str, Any]) -> None:
        return None

    bus.subscribe("policy.evaluated", h)
    bus.subscribe("workflow.completed", h)
    assert bus.event_names() == ["policy.evaluated", "workflow.completed"]
