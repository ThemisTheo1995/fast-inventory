import uuid
from datetime import UTC, datetime

from erp.api.modules.bin.schemas.bin import BinResponse
from erp.api.modules.inventory.schemas.inventory_expanded import (
    InventoryExpandedPaginatedResponse,
    InventoryExpandedResponse,
)
from erp.api.modules.item.schemas import ItemResponse

# ==============================================================================
# EXPANDED INVENTORY RESPONSE
# ==============================================================================


def test_inventory_expanded_response_without_relationships(inventory_data):
    """Expanded relationships are optional."""
    response = InventoryExpandedResponse(**inventory_data)

    assert response.id == inventory_data["id"]
    assert response.item is None
    assert response.bin is None


def test_inventory_expanded_response_accepts_item_and_bin(inventory_data):
    """Verifies expanded response supports item and bin relationships."""
    item = ItemResponse.model_construct()
    bin_response = BinResponse.model_construct()

    response = InventoryExpandedResponse(
        **inventory_data,
        item=item,
        bin=bin_response,
    )

    assert response.item is item
    assert response.bin is bin_response


def test_inventory_expanded_response_inherits_inventory_fields(inventory_data):
    response = InventoryExpandedResponse(**inventory_data)

    assert response.quantity_on_hand == inventory_data["quantity_on_hand"]
    assert response.bin_id == inventory_data["bin_id"]
    assert response.item_id == inventory_data["item_id"]


def test_inventory_expanded_paginated_response():
    now = datetime.now(UTC)

    inventory = InventoryExpandedResponse(
        id=uuid.uuid4(),
        created_at=now,
        updated_at=now,
        is_deleted=False,
        workspace_id=uuid.uuid4(),
        item_id=uuid.uuid4(),
        bin_id=uuid.uuid4(),
        quantity_on_hand=20,
    )

    response = InventoryExpandedPaginatedResponse(
        items=[inventory],
        total=1,
    )

    assert response.total == 1
    assert len(response.items) == 1
    assert response.items[0].quantity_on_hand == 20
    assert response.filters == []


def test_inventory_expanded_paginated_response_empty():
    response = InventoryExpandedPaginatedResponse(
        items=[],
        total=0,
    )

    assert response.items == []
    assert response.total == 0
    assert response.filters == []
