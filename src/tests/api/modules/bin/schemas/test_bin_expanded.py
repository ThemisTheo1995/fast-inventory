import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from erp.api.modules.bin.schemas.bin_expanded import (
    BinExpandedResponse,
    BinInventoryItemResponse,
    ItemSummary,
)


def test_item_summary_from_attributes():
    class ItemObject:
        id = uuid.uuid4()
        title = "Test Item"
        sku = "TEST-001"
        unit_of_measure = "pcs"

    response = ItemSummary.model_validate(ItemObject())

    assert response.id == ItemObject.id
    assert response.title == "Test Item"
    assert response.sku == "TEST-001"
    assert response.unit_of_measure == "pcs"


def test_item_summary_without_unit_of_measure():
    class ItemObject:
        id = uuid.uuid4()
        title = "Test Item"
        sku = "TEST-001"

    response = ItemSummary.model_validate(ItemObject())

    assert response.unit_of_measure is None


def test_bin_inventory_item_response_from_attributes():
    now = datetime.now(UTC)

    class InventoryObject:
        id = uuid.uuid4()
        quantity_on_hand = 15
        item_id = uuid.uuid4()
        created_at = now
        updated_at = now
        item = None

    response = BinInventoryItemResponse.model_validate(InventoryObject())

    assert response.id == InventoryObject.id
    assert response.quantity_on_hand == 15
    assert response.item_id == InventoryObject.item_id
    assert response.item is None


def test_bin_inventory_item_response_with_nested_item():
    now = datetime.now(UTC)

    class ItemObject:
        id = uuid.uuid4()
        title = "Test Item"
        sku = "TEST-001"
        unit_of_measure = "pcs"

    class InventoryObject:
        id = uuid.uuid4()
        quantity_on_hand = 20
        item_id = ItemObject.id
        item = ItemObject()
        created_at = now
        updated_at = now

    response = BinInventoryItemResponse.model_validate(InventoryObject())

    assert response.quantity_on_hand == 20
    assert response.item is not None
    assert response.item.title == "Test Item"
    assert response.item.sku == "TEST-001"


def test_bin_expanded_response_with_inventory_items():
    now = datetime.now(UTC)
    bin_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    item_id = uuid.uuid4()

    item = SimpleNamespace(
        id=item_id,
        title="Test Item",
        sku="TEST-001",
        unit_of_measure="pcs",
    )

    inventory = SimpleNamespace(
        id=uuid.uuid4(),
        quantity_on_hand=25,
        item_id=item_id,
        item=item,
        created_at=now,
        updated_at=now,
    )

    bin_obj = SimpleNamespace(
        id=bin_id,
        workspace_id=workspace_id,
        code="A-01",
        zone="Warehouse A",
        created_at=now,
        updated_at=now,
        inventory_items=[inventory],
    )

    response = BinExpandedResponse.model_validate(bin_obj)

    assert response.id == bin_id
    assert response.workspace_id == workspace_id
    assert len(response.inventory_items) == 1
    assert response.inventory_items[0].quantity_on_hand == 25
    assert response.inventory_items[0].item.title == "Test Item"
    assert response.inventory_items[0].item.sku == "TEST-001"
    assert response.id == bin_id
    assert response.workspace_id == workspace_id
    assert len(response.inventory_items) == 1

    inventory = response.inventory_items[0]
    assert inventory.quantity_on_hand == 25
    assert inventory.item.title == "Test Item"


def test_bin_expanded_response_defaults_to_empty_inventory():
    now = datetime.now(UTC)

    response = BinExpandedResponse(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        code="A-01",
        zone=None,
        created_at=now,
        updated_at=now,
    )

    assert response.inventory_items == []
