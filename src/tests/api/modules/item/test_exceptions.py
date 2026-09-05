from src.erp.api.modules.item.exceptions import ItemExistsError, ItemNotFoundError
from src.erp.core.exceptions import BaseAppError

# ============================================================================
# Exception Subclass Tests
# ============================================================================


def test_item_not_found_error():
    """Verifies ItemNotFoundError initializes with 404 status code and expected detail."""
    err = ItemNotFoundError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == 404
    assert err.detail == "Item not found."


def test_item_exists_error():
    """Verifies ItemExistsError initializes with 409 status code and expected detail."""
    err = ItemExistsError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == 409
    assert err.detail == "Item with received SKU already exists."
