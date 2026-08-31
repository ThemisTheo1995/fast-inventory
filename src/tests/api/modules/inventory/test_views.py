import uuid

from fastapi import status

from src.erp.api.modules.inventory.enums import OrderType

# ==============================================================================
# INVENTORY ENDPOINTS
# ==============================================================================


def test_router_get_inventories_list(client, seed_workspace, active_item):  # noqa
    """Verifies fetching a paginated list of inventory balances."""
    # Active item creation automatically initializes inventory in ItemService,
    # so we should have at least 1 inventory record.
    response = client.get(f"/{seed_workspace}/inventory")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


def test_router_get_inventory_by_item(client, seed_workspace, active_item):
    """Verifies fetching a specific item's inventory balance."""
    response = client.get(f"/{seed_workspace}/inventory/items/{active_item.id}")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "id" in data
    assert data["quantity_on_hand"] >= 0
    assert data["quantity_allocated"] >= 0


def test_router_get_inventory_tenant_isolation(client, alt_workspace, active_item):
    """Verifies inventory cannot be fetched across workspaces."""
    response = client.get(f"/{alt_workspace}/inventory/items/{active_item.id}")
    assert response.status_code in (status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN)


# ==============================================================================
# STOCK MOVEMENT ENDPOINTS
# ==============================================================================


def test_router_create_stock_movement(client, seed_workspace, active_item):
    """Verifies a user can create a manual stock movement."""
    payload = {
        "item_id": str(active_item.id),
        "quantity_change": 50,
        "reference_type": OrderType.MANUAL_ADJUSTMENT.value,
        "notes": "Initial stock count",
    }

    response = client.post(f"/{seed_workspace}/inventory/movements", json=payload)
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["quantity_change"] == 50
    assert data["reference_type"] == OrderType.MANUAL_ADJUSTMENT.value


def test_router_create_stock_movement_insufficient_stock_fails(client, seed_workspace, active_item):
    """Verifies creating a movement that drops stock below 0 returns a 400 error."""
    # Assuming the active item starts at 0 stock
    payload = {
        "item_id": str(active_item.id),
        "quantity_change": -10,  # Negative change without stock
        "reference_type": OrderType.MANUAL_ADJUSTMENT.value,
    }

    response = client.post(f"/{seed_workspace}/inventory/movements", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_router_get_stock_movements_list(client, seed_workspace, active_item):
    """Verifies fetching a list of stock movements, with pagination and item filters."""
    # Create a movement first
    client.post(
        f"/{seed_workspace}/inventory/movements",
        json={
            "item_id": str(active_item.id),
            "quantity_change": 10,
            "reference_type": OrderType.MANUAL_ADJUSTMENT.value,
        },
    )

    # 1. Get all movements
    response = client.get(f"/{seed_workspace}/inventory/movements")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["total"] >= 1

    # 2. Filter by item_id
    response_filtered = client.get(f"/{seed_workspace}/inventory/movements", params={"item_id": str(active_item.id)})
    assert response_filtered.status_code == status.HTTP_200_OK
    assert response_filtered.json()["total"] >= 1

    # 3. Filter by missing item_id
    fake_item_id = uuid.uuid4()
    response_empty = client.get(f"/{seed_workspace}/inventory/movements", params={"item_id": str(fake_item_id)})
    assert response_empty.status_code == status.HTTP_200_OK
    assert response_empty.json()["total"] == 0
