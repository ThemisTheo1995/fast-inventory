import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from erp.api.modules.inventory.enums import StockMovementType
from erp.api.modules.inventory.schemas.stock_movement import (
    StockMovementCreate,
    StockMovementPaginatedResponse,
    StockMovementResponse,
)

# ==============================================================================
# STOCK MOVEMENT CREATE SCHEMA
# ==============================================================================


def test_stock_movement_create_valid_data():
    item_id = uuid.uuid4()
    bin_id = uuid.uuid4()
    reference_id = uuid.uuid4()

    movement = StockMovementCreate(
        item_id=item_id,
        bin_id=bin_id,
        quantity_change=10,
        reference_type=StockMovementType.MANUAL_ADJUSTMENT,
        reference_id=reference_id,
        notes="Stock received",
    )

    assert movement.item_id == item_id
    assert movement.bin_id == bin_id
    assert movement.quantity_change == 10
    assert movement.reference_type == StockMovementType.MANUAL_ADJUSTMENT
    assert movement.reference_id == reference_id
    assert movement.notes == "Stock received"


def test_stock_movement_create_requires_item_id():
    with pytest.raises(ValidationError):
        StockMovementCreate(
            bin_id=uuid.uuid4(),
            quantity_change=10,
            reference_type=StockMovementType.MANUAL_ADJUSTMENT,
        )


def test_stock_movement_create_requires_bin_id():
    with pytest.raises(ValidationError):
        StockMovementCreate(
            item_id=uuid.uuid4(),
            quantity_change=10,
            reference_type=StockMovementType.MANUAL_ADJUSTMENT,
        )


def test_stock_movement_create_requires_quantity_change():
    with pytest.raises(ValidationError):
        StockMovementCreate(
            item_id=uuid.uuid4(),
            bin_id=uuid.uuid4(),
            reference_type=StockMovementType.MANUAL_ADJUSTMENT,
        )


def test_stock_movement_create_requires_reference_type():
    with pytest.raises(ValidationError):
        StockMovementCreate(
            item_id=uuid.uuid4(),
            bin_id=uuid.uuid4(),
            quantity_change=10,
        )


def test_stock_movement_create_optional_fields_default_to_none():
    movement = StockMovementCreate(
        item_id=uuid.uuid4(),
        bin_id=uuid.uuid4(),
        quantity_change=10,
        reference_type=StockMovementType.MANUAL_ADJUSTMENT,
    )

    assert movement.reference_id is None
    assert movement.notes is None


def test_stock_movement_create_allows_negative_quantity_change():
    """Negative changes are valid; the service checks available stock."""
    movement = StockMovementCreate(
        item_id=uuid.uuid4(),
        bin_id=uuid.uuid4(),
        quantity_change=-5,
        reference_type=StockMovementType.MANUAL_ADJUSTMENT,
    )

    assert movement.quantity_change == -5


def test_stock_movement_create_allows_zero_quantity_change():
    """The schema does not currently enforce non-zero movements."""
    movement = StockMovementCreate(
        item_id=uuid.uuid4(),
        bin_id=uuid.uuid4(),
        quantity_change=0,
        reference_type=StockMovementType.MANUAL_ADJUSTMENT,
    )

    assert movement.quantity_change == 0


# ==============================================================================
# STOCK MOVEMENT RESPONSE SCHEMA
# ==============================================================================


def test_stock_movement_response_valid_data(stock_movement_data):
    response = StockMovementResponse(**stock_movement_data)

    assert response.id == stock_movement_data["id"]
    assert response.workspace_id == stock_movement_data["workspace_id"]
    assert response.item_id == stock_movement_data["item_id"]
    assert response.bin_id == stock_movement_data["bin_id"]
    assert response.quantity_change == 10
    assert response.reference_type == StockMovementType.MANUAL_ADJUSTMENT
    assert response.reference_id == stock_movement_data["reference_id"]
    assert response.notes == "Initial stock adjustment"


def test_stock_movement_response_optional_fields(stock_movement_data):
    data = stock_movement_data.copy()
    data["reference_id"] = None
    data["notes"] = None

    response = StockMovementResponse(**data)

    assert response.reference_id is None
    assert response.notes is None


def test_stock_movement_response_requires_bin_id(stock_movement_data):
    data = stock_movement_data.copy()
    data["bin_id"] = None

    with pytest.raises(ValidationError):
        StockMovementResponse(**data)


def test_stock_movement_response_supports_from_attributes(stock_movement_data):
    movement_object = SimpleNamespace(**stock_movement_data)

    response = StockMovementResponse.model_validate(movement_object)

    assert response.id == stock_movement_data["id"]
    assert response.bin_id == stock_movement_data["bin_id"]
    assert response.quantity_change == 10


# ==============================================================================
# STOCK MOVEMENT PAGINATED RESPONSE
# ==============================================================================


def test_stock_movement_paginated_response(stock_movement_data):
    movement = StockMovementResponse(**stock_movement_data)

    response = StockMovementPaginatedResponse(
        items=[movement],
        total=1,
    )

    assert response.total == 1
    assert len(response.items) == 1
    assert response.items[0].id == movement.id


def test_stock_movement_paginated_response_empty():
    response = StockMovementPaginatedResponse(
        items=[],
        total=0,
    )

    assert response.items == []
    assert response.total == 0
