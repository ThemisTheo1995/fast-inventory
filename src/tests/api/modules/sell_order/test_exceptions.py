from erp.api.modules.sell_order.exceptions import (
    SellOrderCannotDeleteError,
    SellOrderExistsError,
    SellOrderLineItemChangeError,
    SellOrderLineNotFoundError,
    SellOrderNotEditableError,
    SellOrderNotFoundError,
    SellOrderStatusTerminalError,
    SellOrderStatusTransitionError,
)
from erp.core.exceptions import BaseAppError


def test_sell_order_not_found_error():
    exc = SellOrderNotFoundError()

    assert isinstance(exc, BaseAppError)
    assert exc.status_code == 404
    assert exc.detail == "Sell order not found."


def test_sell_order_exists_error():
    exc = SellOrderExistsError()

    assert isinstance(exc, BaseAppError)
    assert exc.status_code == 409
    assert exc.detail == "Sell order with received SO number already exists."


def test_sell_order_line_not_found_error():
    exc = SellOrderLineNotFoundError()

    assert isinstance(exc, BaseAppError)
    assert exc.status_code == 404
    assert exc.detail == "Sell order line not found."


def test_sell_order_status_terminal_error():
    exc = SellOrderStatusTerminalError("CANCELLED")

    assert isinstance(exc, BaseAppError)
    assert exc.status_code == 409
    assert exc.detail == "Cannot change status from terminal state: CANCELLED"


def test_sell_order_status_transition_error():
    exc = SellOrderStatusTransitionError("DRAFT", "FULFILLED")

    assert isinstance(exc, BaseAppError)
    assert exc.status_code == 409
    assert exc.detail == "Invalid status transition: DRAFT -> FULFILLED"


def test_sell_order_not_editable_error():
    exc = SellOrderNotEditableError("FULFILLED")

    assert isinstance(exc, BaseAppError)
    assert exc.status_code == 409
    assert exc.detail == "Cannot modify lines on a FULFILLED sell order."


def test_sell_order_cannot_delete_error():
    exc = SellOrderCannotDeleteError("CONFIRMED")

    assert isinstance(exc, BaseAppError)
    assert exc.status_code == 409
    assert exc.detail == ("Cannot delete a sell order in CONFIRMED status. Cancel it first.")


def test_sell_order_line_item_change_error():
    exc = SellOrderLineItemChangeError()

    assert isinstance(exc, BaseAppError)
    assert exc.status_code == 409
    assert exc.detail == "Remove the line and add a new one."
