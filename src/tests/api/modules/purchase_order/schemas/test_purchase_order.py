import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from erp.api.modules.purchase_order.enums import POStatusEnum
from erp.api.modules.purchase_order.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
    PurchaseOrderLineResponse,
    PurchaseOrderLineUpdate,
    PurchaseOrderResponse,
    PurchaseOrderUpdate,
)

# ==============================================================================
# Purchase Order Line Tests
# ==============================================================================


def test_purchase_order_line_create_valid():
    item_id = uuid.uuid4()

    line = PurchaseOrderLineCreate(
        item_id=item_id,
        quantity=10,
        unit_cost=250,
    )

    assert line.item_id == item_id
    assert line.quantity == 10
    assert line.unit_cost == 250


def test_purchase_order_line_create_optional_item():
    """A PO line may exist without an associated item."""

    line = PurchaseOrderLineCreate(
        quantity=5,
        unit_cost=100,
    )

    assert line.item_id is None
    assert line.quantity == 5
    assert line.unit_cost == 100


def test_purchase_order_line_create_explicit_none_item():
    line = PurchaseOrderLineCreate(
        item_id=None,
        quantity=5,
        unit_cost=100,
    )

    assert line.item_id is None


def test_purchase_order_line_quantity_validation():
    with pytest.raises(ValidationError) as exc_info:
        PurchaseOrderLineCreate(
            quantity=0,
            unit_cost=100,
        )

    assert "greater than or equal to 1" in str(exc_info.value)


def test_purchase_order_line_negative_quantity_validation():
    with pytest.raises(ValidationError):
        PurchaseOrderLineCreate(
            quantity=-1,
            unit_cost=100,
        )


def test_purchase_order_line_price_validation():
    with pytest.raises(ValidationError) as exc_info:
        PurchaseOrderLineCreate(
            quantity=1,
            unit_cost=-5,
        )

    assert "greater than or equal to 0" in str(exc_info.value)


def test_purchase_order_line_zero_price_allowed():
    line = PurchaseOrderLineCreate(
        quantity=1,
        unit_cost=0,
    )

    assert line.unit_cost == 0


def test_purchase_order_line_update_valid():
    item_id = uuid.uuid4()

    line = PurchaseOrderLineUpdate(
        item_id=item_id,
        quantity=2,
        unit_cost=50,
    )

    assert line.item_id == item_id
    assert line.quantity == 2
    assert line.unit_cost == 50


def test_purchase_order_line_update_requires_quantity():
    with pytest.raises(ValidationError):
        PurchaseOrderLineUpdate(unit_cost=50)


def test_purchase_order_line_update_requires_unit_cost():
    with pytest.raises(ValidationError):
        PurchaseOrderLineUpdate(quantity=2)


def test_purchase_order_line_update_quantity_validation():
    with pytest.raises(ValidationError):
        PurchaseOrderLineUpdate(
            quantity=0,
            unit_cost=50,
        )


# ==============================================================================
# Purchase Order Header Tests
# ==============================================================================


def test_purchase_order_create_valid():
    supplier_id = uuid.uuid4()

    po = PurchaseOrderCreate(
        po_number="PO-2023-001",
        supplier_id=supplier_id,
        status=POStatusEnum.DRAFT,
        purchase_order_lines=[
            {"quantity": 5, "unit_cost": 100},
            {
                "item_id": uuid.uuid4(),
                "quantity": 2,
                "unit_cost": 500,
            },
        ],
    )

    assert po.po_number == "PO-2023-001"
    assert po.supplier_id == supplier_id
    assert po.status == POStatusEnum.DRAFT
    assert len(po.purchase_order_lines) == 2


def test_purchase_order_create_optional_supplier():
    po = PurchaseOrderCreate(
        po_number="PO-NO-SUPPLIER",
        purchase_order_lines=[],
    )

    assert po.supplier_id is None


def test_purchase_order_create_default_status():
    po = PurchaseOrderCreate(
        po_number="PO-DEFAULT",
        purchase_order_lines=[],
    )

    assert po.status == POStatusEnum.DRAFT


def test_purchase_order_create_empty_lines_allowed():
    po = PurchaseOrderCreate(
        po_number="PO-EMPTY",
        purchase_order_lines=[],
    )

    assert po.purchase_order_lines == []


def test_purchase_order_po_number_max_length():
    with pytest.raises(ValidationError) as exc_info:
        PurchaseOrderCreate(
            po_number="A" * 101,
            purchase_order_lines=[],
        )

    assert "100 characters" in str(exc_info.value)


def test_purchase_order_po_number_max_length_boundary():
    po_number = "A" * 100

    po = PurchaseOrderCreate(
        po_number=po_number,
        purchase_order_lines=[],
    )

    assert po.po_number == po_number


def test_purchase_order_po_number_required():
    with pytest.raises(ValidationError):
        PurchaseOrderCreate(
            purchase_order_lines=[],
        )


def test_purchase_order_update_empty_payload():
    update = PurchaseOrderUpdate()

    assert update.po_number is None
    assert update.supplier_id is None
    assert update.status is None


def test_purchase_order_update_partial_payload():
    update = PurchaseOrderUpdate(
        status=POStatusEnum.SENT,
    )

    assert update.po_number is None
    assert update.supplier_id is None
    assert update.status == POStatusEnum.SENT


def test_purchase_order_update_explicit_none_values_allowed():
    update = PurchaseOrderUpdate(
        po_number=None,
        supplier_id=None,
        status=None,
    )

    assert update.po_number is None
    assert update.supplier_id is None
    assert update.status is None


# ==============================================================================
# Response Model Tests
# ==============================================================================


def test_purchase_order_line_response_attributes():
    line_id = uuid.uuid4()
    po_id = uuid.uuid4()

    line_response = PurchaseOrderLineResponse(
        id=line_id,
        purchase_order_id=po_id,
        quantity=5,
        unit_cost=100,
        item=None,
    )

    assert line_response.id == line_id
    assert line_response.purchase_order_id == po_id
    assert line_response.quantity == 5
    assert line_response.unit_cost == 100
    assert line_response.item is None


def test_purchase_order_response_attributes():
    now = datetime.now(UTC)

    line_response = PurchaseOrderLineResponse(
        id=uuid.uuid4(),
        purchase_order_id=uuid.uuid4(),
        quantity=5,
        unit_cost=100,
        item=None,
    )

    po_response = PurchaseOrderResponse(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        po_number="PO-RESP-1",
        total_amount=500,
        status=POStatusEnum.DRAFT,
        created_at=now,
        updated_at=now,
        purchase_order_lines=[line_response],
        supplier=None,
    )

    assert po_response.total_amount == 500
    assert po_response.status == POStatusEnum.DRAFT
    assert len(po_response.purchase_order_lines) == 1
    assert po_response.purchase_order_lines[0].quantity == 5
    assert po_response.supplier is None
