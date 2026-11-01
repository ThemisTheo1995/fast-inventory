import uuid

import pytest
from fastapi import status
from sqlalchemy import select

from erp.api.modules.bin.models import Bin
from erp.api.modules.inventory.enums import StockMovementType
from erp.api.modules.inventory.models import Inventory

# ==============================================================================
# HELPERS
# ==============================================================================


async def get_inventory_record(db_session, workspace_id, item_id, bin_id):
    """Retrieve the inventory balance for an item in a specific bin."""
    result = await db_session.execute(
        select(Inventory).where(
            Inventory.workspace_id == workspace_id,
            Inventory.item_id == item_id,
            Inventory.bin_id == bin_id,
            Inventory.is_deleted.is_(False),
        )
    )
    return result.scalar_one_or_none()


async def create_test_bin(db_session, workspace_id):
    """Create an additional bin for transfer and isolation tests."""
    bin_record = Bin(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        code=f"TEST-{uuid.uuid4().hex[:8].upper()}",
        zone="Test Warehouse",
        is_deleted=False,
    )
    db_session.add(bin_record)
    await db_session.commit()
    await db_session.refresh(bin_record)
    return bin_record


# ==============================================================================
# INVENTORY ENDPOINTS
# ==============================================================================


@pytest.mark.asyncio
@pytest.mark.usefixtures("active_item")
async def test_router_get_inventories_list(client, seed_workspace):
    """Returns a paginated list of inventory balances."""
    response = await client.get(f"/{seed_workspace}/inventory")

    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1

    inventory = data["items"][0]
    assert "item_id" in inventory
    assert "bin_id" in inventory
    assert "quantity_on_hand" in inventory


@pytest.mark.asyncio
@pytest.mark.usefixtures("active_item")
async def test_router_get_inventories_pagination(client, seed_workspace):
    """Accepts valid pagination parameters."""
    response = await client.get(
        f"/{seed_workspace}/inventory",
        params={"page": 1, "limit": 10},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["total"] >= 1
    assert len(response.json()["items"]) <= 10


@pytest.mark.asyncio
@pytest.mark.usefixtures("active_item")
async def test_router_get_inventories_with_expand(client, seed_workspace):
    """Returns related item and bin data when requested."""
    response = await client.get(
        f"/{seed_workspace}/inventory",
        params=[("expand", "item"), ("expand", "bin")],
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["total"] >= 1

    inventory = data["items"][0]
    assert inventory["item"] is not None
    assert inventory["bin"] is not None


@pytest.mark.asyncio
async def test_router_get_inventory_by_id(client, db_session, seed_workspace, seed_bin, active_item):
    """Retrieves one inventory balance by its inventory record ID."""
    inventory = await get_inventory_record(
        db_session,
        seed_workspace,
        active_item.id,
        seed_bin.id,
    )
    assert inventory is not None

    response = await client.get(f"/{seed_workspace}/inventory/{inventory.id}")

    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["id"] == str(inventory.id)
    assert data["item_id"] == str(active_item.id)
    assert data["bin_id"] == str(seed_bin.id)
    assert data["quantity_on_hand"] == inventory.quantity_on_hand


@pytest.mark.asyncio
async def test_router_get_inventory_with_expand(client, db_session, seed_workspace, seed_bin, active_item):
    """Retrieves an inventory balance with its related item and bin."""
    inventory = await get_inventory_record(
        db_session,
        seed_workspace,
        active_item.id,
        seed_bin.id,
    )
    assert inventory is not None

    response = await client.get(
        f"/{seed_workspace}/inventory/{inventory.id}",
        params=[("expand", "item"), ("expand", "bin")],
    )

    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["id"] == str(inventory.id)
    assert data["item"] is not None
    assert data["bin"] is not None


@pytest.mark.asyncio
async def test_router_get_inventory_not_found(client, seed_workspace):
    """Returns 404 when the inventory record does not exist."""
    response = await client.get(f"/{seed_workspace}/inventory/{uuid.uuid4()}")

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_router_get_inventory_tenant_isolation(
    client, db_session, alt_workspace, seed_workspace, seed_bin, active_item
):
    """A workspace cannot retrieve another workspace's inventory record."""
    inventory = await get_inventory_record(
        db_session,
        seed_workspace,
        active_item.id,
        seed_bin.id,
    )
    assert inventory is not None

    response = await client.get(f"/{alt_workspace}/inventory/{inventory.id}")

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
@pytest.mark.usefixtures("active_item")
async def test_router_get_inventories_tenant_isolation(client, alt_workspace):
    """A user cannot access an unauthorized workspace."""
    response = await client.get(f"/{alt_workspace}/inventory")

    assert response.status_code in (
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    )


# ==============================================================================
# STOCK MOVEMENT ENDPOINTS
# ==============================================================================


@pytest.mark.asyncio
async def test_router_create_stock_movement(client, seed_workspace, seed_bin, active_item):
    """Creates a positive manual stock movement in a specific bin."""
    payload = {
        "item_id": str(active_item.id),
        "bin_id": str(seed_bin.id),
        "quantity_change": 50,
        "reference_type": StockMovementType.MANUAL_ADJUSTMENT.value,
        "notes": "Initial stock count",
    }

    response = await client.post(
        f"/{seed_workspace}/inventory/movements",
        json=payload,
    )

    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert data["item_id"] == str(active_item.id)
    assert data["bin_id"] == str(seed_bin.id)
    assert data["quantity_change"] == 50
    assert data["reference_type"] == StockMovementType.MANUAL_ADJUSTMENT.value
    assert data["notes"] == "Initial stock count"


@pytest.mark.asyncio
async def test_router_create_stock_movement_missing_bin_fails(client, seed_workspace, active_item):
    """Rejects a stock movement when the required bin_id is missing."""
    payload = {
        "item_id": str(active_item.id),
        "quantity_change": 10,
        "reference_type": StockMovementType.MANUAL_ADJUSTMENT.value,
    }

    response = await client.post(
        f"/{seed_workspace}/inventory/movements",
        json=payload,
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.asyncio
async def test_router_create_stock_movement_insufficient_stock_fails(client, seed_workspace, seed_bin, active_item):
    """Rejects a negative movement that would take the bin below zero."""
    payload = {
        "item_id": str(active_item.id),
        "bin_id": str(seed_bin.id),
        "quantity_change": -10,
        "reference_type": StockMovementType.MANUAL_ADJUSTMENT.value,
    }

    response = await client.post(
        f"/{seed_workspace}/inventory/movements",
        json=payload,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_router_create_negative_stock_movement(client, seed_workspace, seed_bin, active_item):
    """Allows a negative movement when the bin has sufficient stock."""
    create_response = await client.post(
        f"/{seed_workspace}/inventory/movements",
        json={
            "item_id": str(active_item.id),
            "bin_id": str(seed_bin.id),
            "quantity_change": 30,
            "reference_type": StockMovementType.MANUAL_ADJUSTMENT.value,
        },
    )
    assert create_response.status_code == status.HTTP_201_CREATED

    decrease_response = await client.post(
        f"/{seed_workspace}/inventory/movements",
        json={
            "item_id": str(active_item.id),
            "bin_id": str(seed_bin.id),
            "quantity_change": -10,
            "reference_type": StockMovementType.MANUAL_ADJUSTMENT.value,
        },
    )

    assert decrease_response.status_code == status.HTTP_201_CREATED
    assert decrease_response.json()["quantity_change"] == -10


@pytest.mark.asyncio
@pytest.mark.usefixtures("seed_workspace")
async def test_router_create_stock_movement_other_workspace_bin_fails(client, alt_workspace, seed_bin, active_item):
    """Rejects using a bin that does not belong to the requested workspace."""
    response = await client.post(
        f"/{alt_workspace}/inventory/movements",
        json={
            "item_id": str(active_item.id),
            "bin_id": str(seed_bin.id),
            "quantity_change": 10,
            "reference_type": StockMovementType.MANUAL_ADJUSTMENT.value,
        },
    )

    assert response.status_code in (
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_404_NOT_FOUND,
    )


@pytest.mark.asyncio
async def test_router_get_stock_movements_list(client, seed_workspace, seed_bin, active_item):
    """Returns stock movements and supports filtering by item."""
    create_response = await client.post(
        f"/{seed_workspace}/inventory/movements",
        json={
            "item_id": str(active_item.id),
            "bin_id": str(seed_bin.id),
            "quantity_change": 10,
            "reference_type": StockMovementType.MANUAL_ADJUSTMENT.value,
        },
    )
    assert create_response.status_code == status.HTTP_201_CREATED

    response = await client.get(f"/{seed_workspace}/inventory/movements")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["total"] >= 1

    filtered_response = await client.get(
        f"/{seed_workspace}/inventory/movements",
        params={"item_id": str(active_item.id)},
    )

    assert filtered_response.status_code == status.HTTP_200_OK
    assert filtered_response.json()["total"] >= 1

    fake_item_id = uuid.uuid4()
    empty_response = await client.get(
        f"/{seed_workspace}/inventory/movements",
        params={"item_id": str(fake_item_id)},
    )

    assert empty_response.status_code == status.HTTP_200_OK
    assert empty_response.json()["total"] == 0


@pytest.mark.asyncio
async def test_router_get_stock_movements_filter_by_bin(client, seed_workspace, seed_bin, active_item, db_session):
    """Filters stock movements by bin."""
    other_bin = await create_test_bin(db_session, seed_workspace)

    first_response = await client.post(
        f"/{seed_workspace}/inventory/movements",
        json={
            "item_id": str(active_item.id),
            "bin_id": str(seed_bin.id),
            "quantity_change": 10,
            "reference_type": StockMovementType.MANUAL_ADJUSTMENT.value,
        },
    )
    second_response = await client.post(
        f"/{seed_workspace}/inventory/movements",
        json={
            "item_id": str(active_item.id),
            "bin_id": str(other_bin.id),
            "quantity_change": 20,
            "reference_type": StockMovementType.MANUAL_ADJUSTMENT.value,
        },
    )

    assert first_response.status_code == status.HTTP_201_CREATED
    assert second_response.status_code == status.HTTP_201_CREATED

    response = await client.get(
        f"/{seed_workspace}/inventory/movements",
        params={"bin_id": str(seed_bin.id)},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["total"] == 1
    assert data["items"][0]["bin_id"] == str(seed_bin.id)


@pytest.mark.asyncio
async def test_router_get_stock_movements_pagination(client, seed_workspace, seed_bin, active_item):
    """Paginates stock movements using page and limit."""
    for quantity in (10, 20, 30):
        response = await client.post(
            f"/{seed_workspace}/inventory/movements",
            json={
                "item_id": str(active_item.id),
                "bin_id": str(seed_bin.id),
                "quantity_change": quantity,
                "reference_type": StockMovementType.MANUAL_ADJUSTMENT.value,
            },
        )
        assert response.status_code == status.HTTP_201_CREATED

    first_page = await client.get(
        f"/{seed_workspace}/inventory/movements",
        params={"page": 1, "limit": 2},
    )
    second_page = await client.get(
        f"/{seed_workspace}/inventory/movements",
        params={"page": 2, "limit": 2},
    )

    assert first_page.status_code == status.HTTP_200_OK
    assert second_page.status_code == status.HTTP_200_OK

    first_data = first_page.json()
    second_data = second_page.json()

    assert first_data["total"] == 3
    assert len(first_data["items"]) == 2
    assert len(second_data["items"]) == 1

    first_page_ids = {item["id"] for item in first_data["items"]}
    second_page_ids = {item["id"] for item in second_data["items"]}

    assert first_page_ids.isdisjoint(second_page_ids)


@pytest.mark.asyncio
async def test_router_get_stock_movements_invalid_pagination(client, seed_workspace):
    """Rejects invalid movement pagination parameters."""
    response = await client.get(
        f"/{seed_workspace}/inventory/movements",
        params={"page": 0, "limit": 101},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# ==============================================================================
# BIN-TO-BIN TRANSFER ENDPOINT
# ==============================================================================


@pytest.mark.asyncio
async def test_router_transfer_stock_between_bins(client, db_session, seed_workspace, seed_bin, active_item):
    """Transfers stock from one bin to another."""
    destination_bin = await create_test_bin(db_session, seed_workspace)

    stock_response = await client.post(
        f"/{seed_workspace}/inventory/movements",
        json={
            "item_id": str(active_item.id),
            "bin_id": str(seed_bin.id),
            "quantity_change": 50,
            "reference_type": StockMovementType.MANUAL_ADJUSTMENT.value,
        },
    )
    assert stock_response.status_code == status.HTTP_201_CREATED

    transfer_response = await client.post(
        f"/{seed_workspace}/inventory/transfer-bin-to-bin",
        json={
            "item_id": str(active_item.id),
            "source_bin_id": str(seed_bin.id),
            "destination_bin_id": str(destination_bin.id),
            "quantity": 20,
            "notes": "Move stock to destination bin",
        },
    )

    assert transfer_response.status_code == status.HTTP_200_OK
    assert transfer_response.json()["message"] == "Stock transferred successfully"

    source_inventory = await get_inventory_record(
        db_session,
        seed_workspace,
        active_item.id,
        seed_bin.id,
    )
    destination_inventory = await get_inventory_record(
        db_session,
        seed_workspace,
        active_item.id,
        destination_bin.id,
    )

    assert source_inventory.quantity_on_hand == 30
    assert destination_inventory.quantity_on_hand == 20


@pytest.mark.asyncio
async def test_router_transfer_all_stock_between_bins(client, db_session, seed_workspace, seed_bin, active_item):
    """A full transfer leaves the source inventory record with zero stock."""
    destination_bin = await create_test_bin(db_session, seed_workspace)

    stock_response = await client.post(
        f"/{seed_workspace}/inventory/movements",
        json={
            "item_id": str(active_item.id),
            "bin_id": str(seed_bin.id),
            "quantity_change": 25,
            "reference_type": StockMovementType.MANUAL_ADJUSTMENT.value,
        },
    )
    assert stock_response.status_code == status.HTTP_201_CREATED

    transfer_response = await client.post(
        f"/{seed_workspace}/inventory/transfer-bin-to-bin",
        json={
            "item_id": str(active_item.id),
            "source_bin_id": str(seed_bin.id),
            "destination_bin_id": str(destination_bin.id),
            "quantity": 25,
        },
    )

    assert transfer_response.status_code == status.HTTP_200_OK

    source_inventory = await get_inventory_record(
        db_session,
        seed_workspace,
        active_item.id,
        seed_bin.id,
    )
    destination_inventory = await get_inventory_record(
        db_session,
        seed_workspace,
        active_item.id,
        destination_bin.id,
    )

    assert source_inventory is not None
    assert source_inventory.quantity_on_hand == 0
    assert destination_inventory.quantity_on_hand == 25


@pytest.mark.asyncio
async def test_router_transfer_insufficient_stock_fails(client, db_session, seed_workspace, seed_bin, active_item):
    """Rejects a transfer larger than the source bin's available stock."""
    destination_bin = await create_test_bin(db_session, seed_workspace)

    response = await client.post(
        f"/{seed_workspace}/inventory/transfer-bin-to-bin",
        json={
            "item_id": str(active_item.id),
            "source_bin_id": str(seed_bin.id),
            "destination_bin_id": str(destination_bin.id),
            "quantity": 10,
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_router_transfer_same_bin_fails(client, seed_workspace, seed_bin, active_item):
    """Rejects a transfer where source and destination are the same bin."""
    response = await client.post(
        f"/{seed_workspace}/inventory/transfer-bin-to-bin",
        json={
            "item_id": str(active_item.id),
            "source_bin_id": str(seed_bin.id),
            "destination_bin_id": str(seed_bin.id),
            "quantity": 10,
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_router_transfer_zero_quantity_fails(client, seed_workspace, seed_bin, active_item, db_session):
    """Rejects a transfer with a quantity of zero at schema validation."""
    destination_bin = await create_test_bin(db_session, seed_workspace)

    response = await client.post(
        f"/{seed_workspace}/inventory/transfer-bin-to-bin",
        json={
            "item_id": str(active_item.id),
            "source_bin_id": str(seed_bin.id),
            "destination_bin_id": str(destination_bin.id),
            "quantity": 0,
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
