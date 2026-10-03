from erp.api.modules.inventory.exceptions import InsufficientInventoryError
from erp.core.exceptions import BaseAppError


def test_insufficient_inventory_error():
    """Verifies InsufficientInventoryError initializes correctly."""
    err = InsufficientInventoryError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == 400
    assert err.detail == "Not enough stock. This movement would make the stock quantity go below zero."
