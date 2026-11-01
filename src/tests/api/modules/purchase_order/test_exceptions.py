import re

import pytest

from erp.api.modules.purchase_order.exceptions import (
    PurchaseOrderCannotDeleteError,
    PurchaseOrderExistsError,
    PurchaseOrderLineItemChangeError,
    PurchaseOrderLineNotFoundError,
    PurchaseOrderNotEditableError,
    PurchaseOrderNotFoundError,
    PurchaseOrderStatusTransitionError,
)
from erp.core.exceptions import BaseAppError

# ============================================================================
# BaseAppError Exception Subclass Tests
# ============================================================================


def test_purchase_order_not_found_error():
    err = PurchaseOrderNotFoundError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == 404
    assert err.detail == "Purchase order not found."


def test_purchase_order_exists_error():
    err = PurchaseOrderExistsError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == 409
    assert err.detail == "Purchase order with received PO number already exists."


def test_purchase_order_line_not_found_error():
    err = PurchaseOrderLineNotFoundError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == 404
    assert err.detail == "Purchase order line not found."


def test_purchase_order_line_item_change_error():
    err = PurchaseOrderLineItemChangeError()

    assert isinstance(err, BaseAppError)
    assert err.status_code == 409
    assert err.detail == "Remove the line and add a new one."


def test_purchase_order_not_editable_error():
    status = "RECEIVED"
    err = PurchaseOrderNotEditableError(status=status)

    assert isinstance(err, BaseAppError)
    assert err.status_code == 409
    assert err.detail == f"Cannot modify lines on a {status} purchase order."


def test_purchase_order_status_transition_error():
    old_status = "DRAFT"
    new_status = "RETURNED"

    err = PurchaseOrderStatusTransitionError(
        old_status=old_status,
        new_status=new_status,
    )

    assert isinstance(err, BaseAppError)
    assert err.status_code == 409
    assert err.detail == f"Invalid status transition: {old_status} -> {new_status}"


# ============================================================================
# ValueError Exception Subclass Tests
# ============================================================================


@pytest.mark.parametrize(
    "status_label",
    [
        "DRAFT",
        "SENT",
        "IN_TRANSIT",
        "RECEIVED",
        "RETURNED",
        "CANCELLED",
        "CLOSED",
    ],
)
def test_purchase_order_cannot_delete_error_formatting(status_label: str):
    err = PurchaseOrderCannotDeleteError(status_label=status_label)

    expected_msg = f"Cannot delete purchase order in status: {status_label}. Cancel the order first."

    assert isinstance(err, ValueError)
    assert not isinstance(err, BaseAppError)
    assert str(err) == expected_msg


def test_purchase_order_cannot_delete_error_raises():
    status_label = "RECEIVED"

    expected_msg = f"Cannot delete purchase order in status: {status_label}. Cancel the order first."

    with pytest.raises(
        PurchaseOrderCannotDeleteError,
        match=re.escape(expected_msg),
    ):
        raise PurchaseOrderCannotDeleteError(status_label=status_label)
