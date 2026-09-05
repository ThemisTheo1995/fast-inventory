import inspect
from collections import defaultdict
from collections.abc import Callable


class EventBus:
    """A lightweight, asynchronous, in-memory event bus."""

    def __init__(self) -> None:
        self._subscribers: dict[type, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Callable) -> None:
        self._subscribers[event_type].append(handler)

    async def publish(self, event: object) -> None:
        for handler in self._subscribers.get(type(event), []):
            if inspect.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)


global_event_bus = EventBus()
