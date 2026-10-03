from erp.api.modules.sell_order.exceptions import (
    SellOrderExistsError,
    SellOrderLineNotFoundError,
    SellOrderNotFoundError,
)
from erp.core.exceptions import BaseAppError


def test_sell_order_not_found_error():
    """Verifies the SellOrderNotFoundError initializes with correct 404 status and message."""
    exc = SellOrderNotFoundError()

    assert isinstance(exc, BaseAppError)
    assert exc.status_code == 404
    assert exc.detail == "Sell order not found."


def test_sell_order_exists_error():
    """Verifies the SellOrderExistsError initializes with correct 409 status and message."""
    exc = SellOrderExistsError()

    assert isinstance(exc, BaseAppError)
    assert exc.status_code == 409
    assert exc.detail == "Sell order with received SO number already exists."


def test_sell_order_line_not_found_error():
    """Verifies the SellOrderLineNotFoundError initializes with correct 404 status and message."""
    exc = SellOrderLineNotFoundError()

    assert isinstance(exc, BaseAppError)
    assert exc.status_code == 404
    assert exc.detail == "Sell order line not found."
