from unittest.mock import AsyncMock, MagicMock

import pytest

from erp.core.event_bus import EventBus, global_event_bus

# ==============================================================================
# MOCK EVENTS
# ==============================================================================


class DummyEventA:
    pass


class DummyEventB:
    pass


# ==============================================================================
# TESTS
# ==============================================================================


def test_event_bus_subscribe():
    """Verifies that handlers are correctly added to the subscriber dictionary."""
    bus = EventBus()
    handler = MagicMock()

    bus.subscribe(DummyEventA, handler)

    assert handler in bus._subscribers[DummyEventA]
    assert len(bus._subscribers[DummyEventA]) == 1


@pytest.mark.asyncio
async def test_event_bus_publish_calls_subscribers():
    """Verifies that publishing an event calls all subscribed handlers with the event instance."""
    bus = EventBus()
    handler_1 = AsyncMock()
    handler_2 = AsyncMock()

    bus.subscribe(DummyEventA, handler_1)
    bus.subscribe(DummyEventA, handler_2)

    event_instance = DummyEventA()
    await bus.publish(event_instance)

    handler_1.assert_called_once_with(event_instance)
    handler_2.assert_called_once_with(event_instance)


@pytest.mark.asyncio
async def test_event_bus_publish_no_subscribers():
    """Verifies that publishing an event with no subscribers doesn't throw an error."""
    bus = EventBus()
    event_instance = DummyEventA()

    await bus.publish(event_instance)


@pytest.mark.asyncio
async def test_event_bus_event_isolation():
    """Verifies that handlers are only triggered for their specifically subscribed event types."""
    bus = EventBus()
    handler_a = AsyncMock()
    handler_b = AsyncMock()

    bus.subscribe(DummyEventA, handler_a)
    bus.subscribe(DummyEventB, handler_b)

    event_a_instance = DummyEventA()
    await bus.publish(event_a_instance)

    # handler_a should be called, but handler_b should not
    handler_a.assert_called_once_with(event_a_instance)
    handler_b.assert_not_called()


def test_global_event_bus_is_instantiated():
    """Verifies the global_event_bus singleton is properly instantiated."""
    assert isinstance(global_event_bus, EventBus)


@pytest.mark.asyncio
async def test_event_bus_publish_sync_handler():
    """Verifies that publishing an event invokes synchronous handlers."""
    bus = EventBus()
    sync_handler = MagicMock()

    bus.subscribe(DummyEventA, sync_handler)

    event_instance = DummyEventA()
    await bus.publish(event_instance)

    sync_handler.assert_called_once_with(event_instance)
