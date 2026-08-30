from src.erp.core.dependencies import get_event_bus
from src.erp.core.event_bus import global_event_bus


def test_get_event_bus():
    """Verifies that the dependency returns the exact global_event_bus instance."""

    bus = get_event_bus()

    assert bus is global_event_bus
