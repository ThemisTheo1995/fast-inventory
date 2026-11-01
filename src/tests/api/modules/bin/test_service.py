import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from erp.api.modules.bin.exceptions import (
    BinHasInventoryItemsError,
    BinNotFoundError,
)
from erp.api.modules.bin.models import Bin
from erp.api.modules.bin.schemas.bin import BinCreate, BinUpdate
from erp.api.modules.bin.schemas.bin_expanded import BinExpandedResponse
from erp.api.modules.bin.service import BinService
from erp.api.modules.inventory.models import Inventory


@pytest.mark.asyncio
async def test_create_bin(db_session, seed_workspace):
    service = BinService(db_session)

    data = BinCreate(
        code="  new-bin-01  ",
        zone="  Warehouse A  ",
    )

    bin_obj = await service.create_bin(seed_workspace, data)

    assert bin_obj.id is not None
    assert bin_obj.workspace_id == seed_workspace
    assert bin_obj.code == "NEW-BIN-01"
    assert bin_obj.zone == "Warehouse A"


@pytest.mark.asyncio
async def test_get_bins_returns_bins_with_stock_totals(db_session, seed_workspace, seed_bin, active_item):
    inventory = Inventory(
        workspace_id=seed_workspace,
        item_id=active_item.id,
        bin_id=seed_bin.id,
        quantity_on_hand=25,
    )
    db_session.add(inventory)
    await db_session.commit()

    service = BinService(db_session)
    response = await service.get_bins(seed_workspace)

    assert response.total >= 1

    matching_bin = next(item for item in response.items if item.id == seed_bin.id)

    assert matching_bin.quantity_on_hand == 25


@pytest.mark.asyncio
async def test_get_bins_search_by_code(db_session, seed_workspace, seed_bin):
    service = BinService(db_session)

    response = await service.get_bins(
        seed_workspace,
        search=seed_bin.code,
    )

    assert any(item.id == seed_bin.id for item in response.items)


@pytest.mark.asyncio
async def test_get_bins_search_by_zone(db_session, seed_workspace, seed_bin):
    service = BinService(db_session)

    response = await service.get_bins(
        seed_workspace,
        search=seed_bin.zone,
    )

    assert any(item.id == seed_bin.id for item in response.items)


@pytest.mark.asyncio
async def test_get_bins_search_returns_empty_for_no_match(db_session, seed_workspace):
    service = BinService(db_session)

    response = await service.get_bins(
        seed_workspace,
        search="NO-SUCH-BIN-999",
    )

    assert response.total == 0
    assert response.items == []


@pytest.mark.asyncio
async def test_get_bins_pagination(db_session, seed_workspace):
    service = BinService(db_session)

    for index in range(3):
        await service.create_bin(
            seed_workspace,
            BinCreate(code=f"PAGE-{index}", zone="Pagination"),
        )

    first_page = await service.get_bins(
        seed_workspace,
        page=1,
        limit=2,
    )
    second_page = await service.get_bins(
        seed_workspace,
        page=2,
        limit=2,
    )

    assert first_page.total >= 3
    assert len(first_page.items) == 2
    assert len(second_page.items) >= 1

    first_ids = {item.id for item in first_page.items}
    second_ids = {item.id for item in second_page.items}

    assert first_ids.isdisjoint(second_ids)


@pytest.mark.asyncio
async def test_get_bins_empty_inventory_has_zero_quantity(db_session, seed_workspace):
    service = BinService(db_session)

    bin_obj = await service.create_bin(
        seed_workspace,
        BinCreate(code="EMPTY-BIN"),
    )

    response = await service.get_bins(seed_workspace)

    matching_bin = next(item for item in response.items if item.id == bin_obj.id)

    assert matching_bin.quantity_on_hand == 0


@pytest.mark.asyncio
async def test_get_bin_success(db_session, seed_workspace, seed_bin):
    service = BinService(db_session)

    response = await service.get_bin(
        seed_workspace,
        seed_bin.id,
    )

    assert response.id == seed_bin.id
    assert response.code == seed_bin.code


@pytest.mark.asyncio
async def test_get_bin_expanded_includes_inventory_and_item(
    db_session,
    seed_workspace,
    seed_bin,
    active_item,
):
    inventory = Inventory(
        workspace_id=seed_workspace,
        item_id=active_item.id,
        bin_id=seed_bin.id,
        quantity_on_hand=12,
    )

    db_session.add(inventory)
    await db_session.commit()

    # Ensure the relationship is loaded from the database.
    result = await db_session.execute(
        select(Bin)
        .where(Bin.id == seed_bin.id)
        .options(selectinload(Bin.inventory_items).selectinload(Inventory.item))
        .execution_options(populate_existing=True)
    )
    loaded_bin = result.scalar_one()

    assert len(loaded_bin.inventory_items) == 1

    service = BinService(db_session)

    response = await service.get_bin(
        seed_workspace,
        seed_bin.id,
        expand=["inventory_items", "inventory_items.item"],
    )

    assert isinstance(response, BinExpandedResponse)
    assert response.id == seed_bin.id
    assert len(response.inventory_items) == 1

    inventory_response = response.inventory_items[0]

    assert inventory_response.quantity_on_hand == 12
    assert inventory_response.item_id == active_item.id
    assert inventory_response.item is not None
    assert inventory_response.item.id == active_item.id
    assert inventory_response.item.title == active_item.title
    assert inventory_response.item.sku == active_item.sku


@pytest.mark.asyncio
async def test_get_bin_expanded_with_empty_inventory(db_session, seed_workspace, seed_bin):
    service = BinService(db_session)

    response = await service.get_bin(
        seed_workspace,
        seed_bin.id,
        expand=["inventory_items", "inventory_items.item"],
    )

    assert isinstance(response, BinExpandedResponse)
    assert response.inventory_items == []


@pytest.mark.asyncio
async def test_get_bin_not_found(db_session, seed_workspace):
    service = BinService(db_session)

    with pytest.raises(BinNotFoundError):
        await service.get_bin(seed_workspace, uuid.uuid4())


@pytest.mark.asyncio
@pytest.mark.usefixtures("seed_workspace")
async def test_get_bin_does_not_return_bin_from_another_workspace(db_session, seed_bin):
    service = BinService(db_session)

    with pytest.raises(BinNotFoundError):
        await service.get_bin(uuid.uuid4(), seed_bin.id)


@pytest.mark.asyncio
async def test_update_bin(db_session, seed_workspace, seed_bin):
    service = BinService(db_session)

    response = await service.update_bin(
        seed_workspace,
        seed_bin.id,
        BinUpdate(
            code="updated-bin",
            zone="Updated Zone",
        ),
    )

    assert response.code == "UPDATED-BIN"
    assert response.zone == "Updated Zone"


@pytest.mark.asyncio
async def test_update_bin_partial(db_session, seed_workspace, seed_bin):
    original_zone = seed_bin.zone
    service = BinService(db_session)

    response = await service.update_bin(
        seed_workspace,
        seed_bin.id,
        BinUpdate(code="new-code"),
    )

    assert response.code == "NEW-CODE"
    assert response.zone == original_zone


@pytest.mark.asyncio
async def test_update_bin_not_found(db_session, seed_workspace):
    service = BinService(db_session)

    with pytest.raises(BinNotFoundError):
        await service.update_bin(
            seed_workspace,
            uuid.uuid4(),
            BinUpdate(code="UPDATED"),
        )


@pytest.mark.asyncio
async def test_delete_empty_bin(db_session, seed_workspace):
    service = BinService(db_session)

    bin_obj = await service.create_bin(
        seed_workspace,
        BinCreate(code="DELETE-ME"),
    )

    await service.delete_bin(seed_workspace, bin_obj.id)

    with pytest.raises(BinNotFoundError):
        await service.get_bin(seed_workspace, bin_obj.id)


@pytest.mark.asyncio
async def test_delete_bin_with_zero_quantity_inventory(db_session, seed_workspace, seed_bin, active_item):
    inventory = Inventory(
        workspace_id=seed_workspace,
        item_id=active_item.id,
        bin_id=seed_bin.id,
        quantity_on_hand=0,
    )
    db_session.add(inventory)
    await db_session.commit()

    service = BinService(db_session)

    await service.delete_bin(seed_workspace, seed_bin.id)

    with pytest.raises(BinNotFoundError):
        await service.get_bin(seed_workspace, seed_bin.id)


@pytest.mark.asyncio
async def test_delete_bin_with_active_stock_rejected(
    db_session,
    seed_workspace,
    seed_bin,
    active_item,
):
    inventory = Inventory(
        workspace_id=seed_workspace,
        item_id=active_item.id,
        bin_id=seed_bin.id,
        quantity_on_hand=10,
    )
    db_session.add(inventory)
    await db_session.commit()

    service = BinService(db_session)

    with pytest.raises(BinHasInventoryItemsError):
        await service.delete_bin(seed_workspace, seed_bin.id)

    # Verify the bin was not soft-deleted.
    result = await db_session.execute(select(Bin).where(Bin.id == seed_bin.id))
    bin_obj = result.scalar_one()

    assert bin_obj.is_deleted is False
    assert bin_obj.deleted_at is None

    # The bin should remain active after the rejected deletion.
    response = await service.get_bin(seed_workspace, seed_bin.id)

    assert response.id == seed_bin.id


@pytest.mark.asyncio
async def test_delete_bin_not_found(db_session, seed_workspace):
    service = BinService(db_session)

    with pytest.raises(BinNotFoundError):
        await service.delete_bin(seed_workspace, uuid.uuid4())
