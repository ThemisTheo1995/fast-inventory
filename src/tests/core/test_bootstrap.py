from unittest.mock import patch

from erp.core.bootstrap import setup_application_events
from erp.core.event_bus import global_event_bus


@patch("erp.core.bootstrap.register_inventory_handlers")
def test_setup_application_events(mock_register_inventory_handlers):
    """Verifies that application events are correctly registered to the global bus."""

    setup_application_events()

    mock_register_inventory_handlers.assert_called_once_with(global_event_bus)
