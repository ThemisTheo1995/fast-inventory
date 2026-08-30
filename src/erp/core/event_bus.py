# src/erp/api/core/event_bus.py
from collections import defaultdict
from collections.abc import Callable


class EventBus:
    """A lightweight, synchronous, in-memory event bus."""

    def __init__(self) -> None:
        self._subscribers: dict[type, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Callable) -> None:
        self._subscribers[event_type].append(handler)

    def publish(self, event: type) -> None:
        for handler in self._subscribers.get(type(event), []):
            handler(event)


global_event_bus = EventBus()
