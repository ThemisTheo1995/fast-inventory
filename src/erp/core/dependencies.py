# src/erp/api/core/dependencies.py

from erp.core.event_bus import EventBus, global_event_bus


def get_event_bus() -> EventBus:
    return global_event_bus
