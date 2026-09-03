import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.erp.api.modules.purchase_order.enums import POStatusEnum
from src.erp.api.modules.purchase_order.schemas.purchase_order import (
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
    """Verifies a valid line payload parses successfully."""
    item_id = uuid.uuid4()
    payload = {"item_id": item_id, "quantity": 10, "unit_cost": 250}

    line = PurchaseOrderLineCreate(**payload)

    assert line.item_id == item_id
    assert line.quantity == 10
    assert line.unit_cost == 250


def test_purchase_order_line_create_optional_item():
    """Verifies item_id is optional for non-inventory lines."""
    payload = {"quantity": 5, "unit_cost": 100}

    line = PurchaseOrderLineCreate(**payload)

    assert line.item_id is None


def test_purchase_order_line_quantity_validation():
    """Verifies quantity must be >= 1."""
    with pytest.raises(ValidationError) as exc_info:
        PurchaseOrderLineCreate(quantity=0, unit_cost=100)

    assert "Input should be greater than or equal to 1" in str(exc_info.value)


def test_purchase_order_line_price_validation():
    """Verifies unit_cost must be >= 0."""
    with pytest.raises(ValidationError) as exc_info:
        PurchaseOrderLineCreate(quantity=1, unit_cost=-5)

    assert "Input should be greater than or equal to 0" in str(exc_info.value)


def test_purchase_order_line_update():
    """Verifies line update schema inherits base constraints."""
    item_id = uuid.uuid4()
    # Since it inherits PurchaseOrderLineBase directly, quantity and unit_cost are required
    line = PurchaseOrderLineUpdate(item_id=item_id, quantity=2, unit_cost=50)
    assert line.quantity == 2

    with pytest.raises(ValidationError):
        PurchaseOrderLineUpdate(quantity=0, unit_cost=50)  # Invalid quantity


# ==============================================================================
# Purchase Order Header Tests
# ==============================================================================


def test_purchase_order_create_valid():
    """Verifies a valid PO payload with nested lines parses correctly."""
    supplier_id = uuid.uuid4()
    payload = {
        "po_number": "PO-2023-001",
        "supplier_id": supplier_id,
        "status": POStatusEnum.DRAFT,
        "purchase_order_lines": [
            {"quantity": 5, "unit_cost": 100},
            {"item_id": uuid.uuid4(), "quantity": 2, "unit_cost": 500},
        ],
    }

    po = PurchaseOrderCreate(**payload)

    assert po.po_number == "PO-2023-001"
    assert po.supplier_id == supplier_id
    assert po.status == POStatusEnum.DRAFT
    assert len(po.purchase_order_lines) == 2


def test_purchase_order_create_default_status():
    """Verifies status defaults to DRAFT if omitted."""
    payload = {"po_number": "PO-DEFAULT", "purchase_order_lines": []}

    po = PurchaseOrderCreate(**payload)
    assert po.status == POStatusEnum.DRAFT


def test_purchase_order_po_number_max_length():
    """Verifies po_number cannot exceed 100 characters."""
    long_po_number = "A" * 101

    with pytest.raises(ValidationError) as exc_info:
        PurchaseOrderCreate(po_number=long_po_number, purchase_order_lines=[])

    assert "String should have at most 100 characters" in str(exc_info.value)


def test_purchase_order_update_optional_fields():
    """Verifies all fields in PurchaseOrderUpdate are optional."""
    # Empty payload should be valid
    update = PurchaseOrderUpdate()
    assert update.po_number is None
    assert update.supplier_id is None
    assert update.status is None

    # Partial update should be valid
    update_partial = PurchaseOrderUpdate(status=POStatusEnum.SENT)
    assert update_partial.po_number is None
    assert update_partial.status == POStatusEnum.SENT


# ==============================================================================
# Response Model Tests
# ==============================================================================


def test_purchase_order_response_attributes():
    """Verifies response model can be constructed (e.g., from ORM objects)."""
    now = datetime.now(UTC)

    line_response = PurchaseOrderLineResponse(
        id=uuid.uuid4(), purchase_order_id=uuid.uuid4(), quantity=5, unit_cost=100, item=None
    )

    po_response = PurchaseOrderResponse(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        po_number="PO-RESP-1",
        total_amount=500,
        created_at=now,
        updated_at=now,
        purchase_order_lines=[line_response],
        supplier=None,
    )

    assert po_response.total_amount == 500
    assert len(po_response.purchase_order_lines) == 1
    assert po_response.purchase_order_lines[0].quantity == 5
