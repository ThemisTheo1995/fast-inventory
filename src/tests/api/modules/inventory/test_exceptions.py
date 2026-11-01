import pytest

from erp.api.modules.inventory.exceptions import (
    InsufficientInventoryError,
    InventoryNotFoundError,
    PickPackInvalidQuantityError,
    TransferStockQuantityNegativeError,
    TransferStockSameBinError,
)
from erp.core.exceptions import BaseAppError


def test_insufficient_inventory_error():
    """Verifies insufficient physical stock error."""
    err = InsufficientInventoryError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == 400
    assert err.detail == ("Not enough physical stock. This movement would make the stock quantity go below zero.")


def test_inventory_not_found_error():
    """Verifies inventory not found error."""
    err = InventoryNotFoundError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == 404
    assert err.detail == "Inventory not found."


def test_transfer_stock_quantity_negative_error():
    """Verifies invalid transfer quantity error."""
    err = TransferStockQuantityNegativeError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == 400
    assert err.detail == "Transfer quantity must be greater than zero."


def test_transfer_stock_same_bin_error():
    """Verifies transfers between the same bin are rejected."""
    err = TransferStockSameBinError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == 400
    assert err.detail == "Source and destination bins cannot be the same."


def test_pickpack_invalid_quantity_default_message():
    """Verifies pick/pack invalid quantity default message."""
    err = PickPackInvalidQuantityError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == 400
    assert err.detail == "Quantity must be greater than zero."


def test_pickpack_invalid_quantity_custom_message():
    """Verifies pick/pack accepts a custom validation message."""
    message = "Fulfillment quantity must be greater than zero."

    err = PickPackInvalidQuantityError(detail=message)

    assert isinstance(err, BaseAppError)
    assert err.status_code == 400
    assert err.detail == message


@pytest.mark.parametrize(
    "quantity",
    [0, -1, -10],
)
def test_pickpack_invalid_quantity_messages_are_independent(quantity):
    """Verifies custom details are preserved for different invalid quantities."""
    message = f"Invalid quantity: {quantity}"

    err = PickPackInvalidQuantityError(detail=message)

    assert err.detail == message
    assert err.status_code == 400
