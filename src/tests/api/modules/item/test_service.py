import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from erp.api.modules.bin.models import Bin
from erp.api.modules.inventory.exceptions import InsufficientInventoryError
from erp.api.modules.inventory.models import Inventory
from erp.api.modules.item.exceptions import ItemExistsError, ItemNotFoundError
from erp.api.modules.item.models import Item
from erp.api.modules.item.schemas import ItemCreate, ItemUpdate
from erp.api.modules.item.service import ItemService

# ==============================================================================
# HELPERS
# ==============================================================================


async def create_bin_with_stock(
    db_session,
    workspace_id,
    item_id,
    quantity,
    *,
    is_deleted=False,
):
    """Creates a bin and an inventory balance for an item."""
    bin_record = Bin(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        code=f"TEST-{uuid.uuid4().hex[:8].upper()}",
        zone="Test Warehouse",
        is_deleted=False,
    )

    db_session.add(bin_record)
    await db_session.flush()

    inventory = Inventory(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        item_id=item_id,
        bin_id=bin_record.id,
        quantity_on_hand=quantity,
        is_deleted=is_deleted,
    )

    db_session.add(inventory)
    await db_session.commit()
    await db_session.refresh(inventory)

    return bin_record, inventory


async def get_item_record(db_session, workspace_id, item_id):
    """Fetches an item directly from the database."""
    result = await db_session.execute(
        select(Item).where(
            Item.workspace_id == workspace_id,
            Item.id == item_id,
        )
    )
    return result.scalar_one_or_none()


# ==============================================================================
# 1. CREATE
# ==============================================================================


@pytest.mark.asyncio
async def test_create_item_success_does_not_initialize_inventory(
    db_session,
    seed_workspace,
):
    """Creates an item without automatically creating bin inventory."""
    service = ItemService(db_session)

    data = ItemCreate(
        title="New Test Item",
        sku=f"NEW-{uuid.uuid4().hex[:8]}",
        base_price=1000,
    )

    with patch("erp.api.modules.item.service.send_barcode_generation_event") as barcode_event:
        item = await service.create_item(seed_workspace, data)

    assert item is not None
    assert item.title == data.title
    assert item.sku == data.sku
    assert item.workspace_id == seed_workspace
    assert item.barcode_id == f"{seed_workspace}_{data.sku}"

    assert item.quantity_on_order == 0
    assert item.quantity_allocated == 0

    barcode_event.assert_called_once()

    result = await db_session.execute(
        select(Inventory).where(
            Inventory.workspace_id == seed_workspace,
            Inventory.item_id == item.id,
        )
    )

    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_create_item_defaults_base_price_to_zero(
    db_session,
    seed_workspace,
):
    """An omitted base price defaults to zero."""
    service = ItemService(db_session)

    data = ItemCreate(
        title="Free Item",
        sku=f"FREE-{uuid.uuid4().hex[:8]}",
    )

    item = await service.create_item(seed_workspace, data)

    assert item.base_price == 0


@pytest.mark.asyncio
async def test_create_item_generates_barcode(
    db_session,
    seed_workspace,
):
    """Barcode ID is generated from workspace ID and SKU."""
    service = ItemService(db_session)
    sku = f"BARCODE-{uuid.uuid4().hex[:8]}"

    with patch("erp.api.modules.item.service.send_barcode_generation_event") as barcode_event:
        item = await service.create_item(
            seed_workspace,
            ItemCreate(
                title="Barcode Test Item",
                sku=sku,
                base_price=100,
            ),
        )

    expected_barcode = f"{seed_workspace}_{sku}"

    assert item.barcode_id == expected_barcode
    barcode_event.assert_called_once()

    event_payload = barcode_event.call_args.args[0]
    assert event_payload.barcode_id == expected_barcode
    assert event_payload.workspace_id == seed_workspace


@pytest.mark.asyncio
async def test_create_item_duplicate_sku_fails(
    db_session,
    seed_workspace,
    active_item,
):
    """Rejects a duplicate SKU within the same workspace."""
    service = ItemService(db_session)

    data = ItemCreate(
        title="Duplicate Item",
        sku=active_item.sku,
        base_price=100,
    )

    with pytest.raises(ItemExistsError):
        await service.create_item(seed_workspace, data)


@pytest.mark.asyncio
@pytest.mark.usefixtures("seed_workspace")
async def test_create_item_same_sku_allowed_in_different_workspaces(db_session, alt_workspace, active_item):
    """The same SKU can exist in different workspaces."""
    service = ItemService(db_session)

    item = await service.create_item(
        alt_workspace,
        ItemCreate(
            title="Other Workspace Item",
            sku=active_item.sku,
            base_price=200,
        ),
    )

    assert item.workspace_id == alt_workspace
    assert item.sku == active_item.sku
    assert item.id != active_item.id


@pytest.mark.asyncio
async def test_create_item_deleted_sku_still_reserved(
    db_session,
    seed_workspace,
    active_item,
):
    """A soft-deleted item's SKU remains reserved by the database constraint."""
    service = ItemService(db_session)

    await service.delete_item(seed_workspace, active_item.id)

    with pytest.raises(ItemExistsError):
        await service.create_item(
            seed_workspace,
            ItemCreate(
                title="Replacement Item",
                sku=active_item.sku,
                base_price=100,
            ),
        )


# ==============================================================================
# 2. READ SINGLE ITEM
# ==============================================================================


@pytest.mark.asyncio
async def test_get_item_success(
    db_session,
    seed_workspace,
    active_item,
):
    """Fetches an active item by ID."""
    service = ItemService(db_session)

    item = await service.get_item(seed_workspace, active_item.id)

    assert item.id == active_item.id
    assert item.workspace_id == seed_workspace
    assert item.sku == active_item.sku


@pytest.mark.asyncio
async def test_get_item_not_found(
    db_session,
    seed_workspace,
):
    """Raises ItemNotFoundError for a missing item."""
    service = ItemService(db_session)

    with pytest.raises(ItemNotFoundError):
        await service.get_item(seed_workspace, uuid.uuid4())


@pytest.mark.asyncio
async def test_get_item_tenant_isolation(
    db_session,
    alt_workspace,
    active_item,
):
    """An item cannot be retrieved from another workspace."""
    service = ItemService(db_session)

    with pytest.raises(ItemNotFoundError):
        await service.get_item(alt_workspace, active_item.id)


@pytest.mark.asyncio
async def test_get_item_soft_deleted_not_found(
    db_session,
    seed_workspace,
    active_item,
):
    """Soft-deleted items are not returned by get_item."""
    service = ItemService(db_session)

    await service.delete_item(seed_workspace, active_item.id)

    with pytest.raises(ItemNotFoundError):
        await service.get_item(seed_workspace, active_item.id)


# ==============================================================================
# 3. READ LIST, PAGINATION AND SEARCH
# ==============================================================================


@pytest.mark.asyncio
async def test_get_items_returns_workspace_items(
    db_session,
    seed_workspace,
    active_item,
):
    """Lists items belonging to the requested workspace."""
    service = ItemService(db_session)

    response = await service.get_items(seed_workspace)

    returned_ids = {item.id for item in response.items}

    assert active_item.id in returned_ids
    assert response.total >= 1
    assert response.page == 1
    assert response.limit == 20


@pytest.mark.asyncio
async def test_get_items_tenant_isolation(
    db_session,
    alt_workspace,
    active_item,
):
    """Items from another workspace are not included in the listing."""
    service = ItemService(db_session)

    response = await service.get_items(alt_workspace)

    returned_ids = {item.id for item in response.items}

    assert active_item.id not in returned_ids
    assert all(item.workspace_id == alt_workspace for item in response.items)


@pytest.mark.asyncio
async def test_get_items_pagination(
    db_session,
    seed_workspace,
):
    """Returns the correct number of records across pages."""
    service = ItemService(db_session)
    marker = uuid.uuid4().hex[:8]

    for index in range(5):
        await service.create_item(
            seed_workspace,
            ItemCreate(
                title=f"Pagination Item {marker} {index}",
                sku=f"PAGE-{marker}-{index}",
                base_price=100,
            ),
        )

    first_page = await service.get_items(
        workspace_id=seed_workspace,
        search=marker,
        page=1,
        limit=2,
    )

    second_page = await service.get_items(
        workspace_id=seed_workspace,
        search=marker,
        page=2,
        limit=2,
    )

    third_page = await service.get_items(
        workspace_id=seed_workspace,
        search=marker,
        page=3,
        limit=2,
    )

    assert first_page.total == 5
    assert second_page.total == 5
    assert third_page.total == 5

    assert len(first_page.items) == 2
    assert len(second_page.items) == 2
    assert len(third_page.items) == 1

    first_ids = {item.id for item in first_page.items}
    second_ids = {item.id for item in second_page.items}
    third_ids = {item.id for item in third_page.items}

    assert first_ids.isdisjoint(second_ids)
    assert first_ids.isdisjoint(third_ids)
    assert second_ids.isdisjoint(third_ids)


@pytest.mark.asyncio
async def test_get_items_search_by_title(
    db_session,
    seed_workspace,
):
    """Search matches item titles."""
    service = ItemService(db_session)
    marker = uuid.uuid4().hex[:8]

    await service.create_item(
        seed_workspace,
        ItemCreate(
            title=f"Searchable Product {marker}",
            sku=f"TITLE-{marker}",
            base_price=100,
        ),
    )

    response = await service.get_items(
        workspace_id=seed_workspace,
        search=marker,
    )

    assert response.total == 1
    assert response.items[0].title == f"Searchable Product {marker}"


@pytest.mark.asyncio
async def test_get_items_search_by_sku(
    db_session,
    seed_workspace,
):
    """Search matches item SKUs."""
    service = ItemService(db_session)
    sku = f"SEARCH-{uuid.uuid4().hex[:8]}"

    await service.create_item(
        seed_workspace,
        ItemCreate(
            title="Unrelated Product",
            sku=sku,
            base_price=100,
        ),
    )

    response = await service.get_items(
        workspace_id=seed_workspace,
        search=sku,
    )

    assert response.total == 1
    assert response.items[0].sku == sku


@pytest.mark.asyncio
async def test_get_items_search_matches_title_or_sku(
    db_session,
    seed_workspace,
):
    """Search matches either the title or SKU."""
    service = ItemService(db_session)
    marker = uuid.uuid4().hex[:8]

    await service.create_item(
        seed_workspace,
        ItemCreate(
            title=f"Title Match {marker}",
            sku=f"SKU-TITLE-{marker}",
            base_price=100,
        ),
    )

    await service.create_item(
        seed_workspace,
        ItemCreate(
            title=f"Different Product {marker}",
            sku=f"SKU-MATCH-{marker}",
            base_price=100,
        ),
    )

    response = await service.get_items(
        workspace_id=seed_workspace,
        search=marker,
    )

    assert response.total == 2


@pytest.mark.asyncio
async def test_get_items_search_no_matches(
    db_session,
    seed_workspace,
):
    """Returns an empty result when search finds no matching items."""
    service = ItemService(db_session)

    response = await service.get_items(
        workspace_id=seed_workspace,
        search=f"NO-MATCH-{uuid.uuid4().hex}",
    )

    assert response.total == 0
    assert response.items == []


# ==============================================================================
# 4. UPDATE
# ==============================================================================


@pytest.mark.asyncio
async def test_update_item_metadata_success(
    db_session,
    seed_workspace,
    active_item,
):
    """Updates item metadata."""
    service = ItemService(db_session)

    updated = await service.update_item(
        workspace_id=seed_workspace,
        item_id=active_item.id,
        data=ItemUpdate(
            title="Updated Title",
            base_price=9999,
        ),
    )

    assert updated.title == "Updated Title"
    assert updated.base_price == 9999
    assert updated.sku == active_item.sku


@pytest.mark.asyncio
async def test_update_item_partial_update_preserves_other_fields(
    db_session,
    seed_workspace,
    active_item,
):
    """Updating only the title preserves SKU and base price."""
    service = ItemService(db_session)

    original_sku = active_item.sku
    original_price = active_item.base_price

    updated = await service.update_item(
        workspace_id=seed_workspace,
        item_id=active_item.id,
        data=ItemUpdate(title="Only Title Updated"),
    )

    assert updated.title == "Only Title Updated"
    assert updated.sku == original_sku
    assert updated.base_price == original_price


@pytest.mark.asyncio
async def test_update_item_duplicate_sku_fails(
    db_session,
    seed_workspace,
    active_item,
):
    """Rejects changing an item's SKU to one already used in the workspace."""
    service = ItemService(db_session)

    second_item = await service.create_item(
        seed_workspace,
        ItemCreate(
            title="Second Item",
            sku=f"SECOND-{uuid.uuid4().hex[:8]}",
            base_price=100,
        ),
    )

    with pytest.raises(ItemExistsError):
        await service.update_item(
            workspace_id=seed_workspace,
            item_id=second_item.id,
            data=ItemUpdate(sku=active_item.sku),
        )


@pytest.mark.asyncio
async def test_update_item_same_sku_allowed(
    db_session,
    seed_workspace,
    active_item,
):
    """Updating other fields without changing SKU is allowed."""
    service = ItemService(db_session)

    with patch("erp.api.modules.item.service.send_barcode_generation_event") as barcode_event:
        updated = await service.update_item(
            workspace_id=seed_workspace,
            item_id=active_item.id,
            data=ItemUpdate(
                title="New Name",
                sku=active_item.sku,
            ),
        )

    assert updated.title == "New Name"
    assert updated.sku == active_item.sku
    barcode_event.assert_not_called()


@pytest.mark.asyncio
async def test_update_item_sku_regenerates_barcode(
    db_session,
    seed_workspace,
    active_item,
):
    """Changing an SKU generates a new barcode and dispatches the event."""
    service = ItemService(db_session)
    new_sku = f"UPDATED-{uuid.uuid4().hex[:8]}"

    with patch("erp.api.modules.item.service.send_barcode_generation_event") as barcode_event:
        updated = await service.update_item(
            workspace_id=seed_workspace,
            item_id=active_item.id,
            data=ItemUpdate(sku=new_sku),
        )

    expected_barcode = f"{seed_workspace}_{new_sku}"

    assert updated.sku == new_sku
    assert updated.barcode_id == expected_barcode

    barcode_event.assert_called_once()
    event_payload = barcode_event.call_args.args[0]

    assert event_payload.barcode_id == expected_barcode
    assert event_payload.workspace_id == seed_workspace


@pytest.mark.asyncio
async def test_update_item_sku_can_match_another_workspace(
    db_session,
    seed_workspace,
    alt_workspace,
    active_item,
):
    """SKU uniqueness does not cross workspace boundaries."""
    service = ItemService(db_session)

    other_item = await service.create_item(
        alt_workspace,
        ItemCreate(
            title="Other Workspace Item",
            sku=f"OTHER-{uuid.uuid4().hex[:8]}",
            base_price=100,
        ),
    )

    updated = await service.update_item(
        workspace_id=seed_workspace,
        item_id=active_item.id,
        data=ItemUpdate(sku=other_item.sku),
    )

    assert updated.sku == other_item.sku


@pytest.mark.asyncio
async def test_update_item_not_found(
    db_session,
    seed_workspace,
):
    """Updating a nonexistent item raises ItemNotFoundError."""
    service = ItemService(db_session)

    with pytest.raises(ItemNotFoundError):
        await service.update_item(
            workspace_id=seed_workspace,
            item_id=uuid.uuid4(),
            data=ItemUpdate(title="Missing"),
        )


@pytest.mark.asyncio
async def test_update_item_tenant_isolation(
    db_session,
    alt_workspace,
    active_item,
):
    """A workspace cannot update another workspace's item."""
    service = ItemService(db_session)

    with pytest.raises(ItemNotFoundError):
        await service.update_item(
            workspace_id=alt_workspace,
            item_id=active_item.id,
            data=ItemUpdate(title="Unauthorized Update"),
        )

    await db_session.refresh(active_item)
    assert active_item.title == "Active Test Item"


@pytest.mark.asyncio
async def test_update_soft_deleted_item_fails(
    db_session,
    seed_workspace,
    active_item,
):
    """A soft-deleted item cannot be updated without explicitly including is_deleted."""
    service = ItemService(db_session)

    await service.delete_item(seed_workspace, active_item.id)

    with pytest.raises(ItemNotFoundError):
        await service.update_item(
            workspace_id=seed_workspace,
            item_id=active_item.id,
            data=ItemUpdate(title="Should Not Update"),
        )


@pytest.mark.asyncio
async def test_update_item_can_restore_soft_deleted_item(
    db_session,
    seed_workspace,
    active_item,
):
    """Explicitly setting is_deleted=False restores a soft-deleted item."""
    service = ItemService(db_session)

    await service.delete_item(seed_workspace, active_item.id)

    updated = await service.update_item(
        workspace_id=seed_workspace,
        item_id=active_item.id,
        data=ItemUpdate(is_deleted=False),
    )

    assert updated.is_deleted is False
    assert updated.id == active_item.id


# ==============================================================================
# 5. DELETE
# ==============================================================================


@pytest.mark.asyncio
async def test_delete_item_success(
    db_session,
    seed_workspace,
    active_item,
):
    """Soft-deletes an item."""
    service = ItemService(db_session)

    await service.delete_item(seed_workspace, active_item.id)

    await db_session.refresh(active_item)

    assert active_item.is_deleted is True

    with pytest.raises(ItemNotFoundError):
        await service.get_item(seed_workspace, active_item.id)


@pytest.mark.asyncio
async def test_delete_item_not_found(
    db_session,
    seed_workspace,
):
    """Deleting a nonexistent item raises ItemNotFoundError."""
    service = ItemService(db_session)

    with pytest.raises(ItemNotFoundError):
        await service.delete_item(seed_workspace, uuid.uuid4())


@pytest.mark.asyncio
async def test_delete_item_tenant_isolation(
    db_session,
    alt_workspace,
    active_item,
):
    """A workspace cannot delete another workspace's item."""
    service = ItemService(db_session)

    with pytest.raises(ItemNotFoundError):
        await service.delete_item(alt_workspace, active_item.id)

    await db_session.refresh(active_item)
    assert active_item.is_deleted is False


# ==============================================================================
# 6. QUANTITY ON ORDER
# ==============================================================================


@pytest.mark.asyncio
async def test_adjust_quantity_on_order_increases_quantity(
    db_session,
    seed_workspace,
    active_item,
):
    """Increases the item's global incoming quantity."""
    service = ItemService(db_session)

    await service.adjust_quantity_on_order(
        seed_workspace,
        active_item.id,
        10,
    )

    await db_session.refresh(active_item)

    assert active_item.quantity_on_order == 10


@pytest.mark.asyncio
async def test_adjust_quantity_on_order_decreases_quantity(
    db_session,
    seed_workspace,
    active_item,
):
    """Decreases the item's global incoming quantity."""
    service = ItemService(db_session)

    await service.adjust_quantity_on_order(
        seed_workspace,
        active_item.id,
        10,
    )

    await service.adjust_quantity_on_order(
        seed_workspace,
        active_item.id,
        -4,
    )

    await db_session.refresh(active_item)

    assert active_item.quantity_on_order == 6


@pytest.mark.asyncio
async def test_adjust_quantity_on_order_rejects_negative_result(
    db_session,
    seed_workspace,
    active_item,
):
    """Does not allow incoming quantity to become negative."""
    service = ItemService(db_session)

    with pytest.raises(InsufficientInventoryError):
        await service.adjust_quantity_on_order(
            seed_workspace,
            active_item.id,
            -1,
        )

    await db_session.refresh(active_item)
    assert active_item.quantity_on_order == 0


@pytest.mark.asyncio
async def test_adjust_quantity_on_order_zero_delta(
    db_session,
    seed_workspace,
    active_item,
):
    """A zero adjustment does not change the quantity."""
    service = ItemService(db_session)

    await service.adjust_quantity_on_order(
        seed_workspace,
        active_item.id,
        0,
    )

    await db_session.refresh(active_item)

    assert active_item.quantity_on_order == 0


@pytest.mark.asyncio
async def test_adjust_quantity_on_order_zero_delta_does_not_fetch_item(
    db_session,
    seed_workspace,
):
    """A zero adjustment returns without looking up the item."""
    service = ItemService(db_session)

    await service.adjust_quantity_on_order(
        seed_workspace,
        uuid.uuid4(),
        0,
    )


@pytest.mark.asyncio
async def test_adjust_quantity_on_order_item_not_found(
    db_session,
    seed_workspace,
):
    """A nonzero adjustment for a missing item raises ItemNotFoundError."""
    service = ItemService(db_session)

    with pytest.raises(ItemNotFoundError):
        await service.adjust_quantity_on_order(
            seed_workspace,
            uuid.uuid4(),
            5,
        )


@pytest.mark.asyncio
async def test_adjust_quantity_on_order_is_not_committed(
    db_session,
    seed_workspace,
    active_item,
):
    service = ItemService(db_session)
    item_id = active_item.id

    await service.adjust_quantity_on_order(
        seed_workspace,
        item_id,
        10,
    )

    quantity = await db_session.scalar(
        select(Item.quantity_on_order).where(
            Item.id == item_id,
            Item.workspace_id == seed_workspace,
        )
    )
    assert quantity == 10

    await db_session.rollback()

    quantity = await db_session.scalar(
        select(Item.quantity_on_order).where(
            Item.id == item_id,
            Item.workspace_id == seed_workspace,
        )
    )
    assert quantity == 0


# ==============================================================================
# 7. QUANTITY ALLOCATED
# ==============================================================================


@pytest.mark.asyncio
async def test_adjust_quantity_allocated_success(
    db_session,
    seed_workspace,
    active_item,
):
    """Allocates stock when sufficient physical stock exists."""
    service = ItemService(db_session)

    await create_bin_with_stock(
        db_session,
        seed_workspace,
        active_item.id,
        quantity=20,
    )

    await service.adjust_quantity_allocated(
        seed_workspace,
        active_item.id,
        10,
    )

    await db_session.refresh(active_item)

    assert active_item.quantity_allocated == 10


@pytest.mark.asyncio
async def test_adjust_quantity_allocated_across_multiple_bins(
    db_session,
    seed_workspace,
    active_item,
):
    """Available physical stock is summed across multiple bins."""
    service = ItemService(db_session)

    await create_bin_with_stock(
        db_session,
        seed_workspace,
        active_item.id,
        quantity=5,
    )

    await create_bin_with_stock(
        db_session,
        seed_workspace,
        active_item.id,
        quantity=7,
    )

    await service.adjust_quantity_allocated(
        seed_workspace,
        active_item.id,
        12,
    )

    await db_session.refresh(active_item)

    assert active_item.quantity_allocated == 12


@pytest.mark.asyncio
async def test_adjust_quantity_allocated_rejects_insufficient_stock(
    db_session,
    seed_workspace,
    active_item,
):
    """Rejects allocation exceeding total physical stock."""
    service = ItemService(db_session)

    await create_bin_with_stock(
        db_session,
        seed_workspace,
        active_item.id,
        quantity=5,
    )

    with pytest.raises(InsufficientInventoryError):
        await service.adjust_quantity_allocated(
            seed_workspace,
            active_item.id,
            6,
        )

    await db_session.refresh(active_item)
    assert active_item.quantity_allocated == 0


@pytest.mark.asyncio
async def test_adjust_quantity_allocated_accounts_for_existing_allocations(
    db_session,
    seed_workspace,
    active_item,
):
    """Only unallocated physical stock can be newly allocated."""
    service = ItemService(db_session)

    await create_bin_with_stock(
        db_session,
        seed_workspace,
        active_item.id,
        quantity=10,
    )

    active_item.quantity_allocated = 7
    await db_session.commit()

    with pytest.raises(InsufficientInventoryError):
        await service.adjust_quantity_allocated(
            seed_workspace,
            active_item.id,
            4,
        )

    await db_session.refresh(active_item)
    assert active_item.quantity_allocated == 7


@pytest.mark.asyncio
async def test_adjust_quantity_allocated_decreases_quantity(
    db_session,
    seed_workspace,
    active_item,
):
    """Decreases existing allocation."""
    service = ItemService(db_session)

    await create_bin_with_stock(
        db_session,
        seed_workspace,
        active_item.id,
        quantity=20,
    )

    active_item.quantity_allocated = 10
    await db_session.commit()

    await service.adjust_quantity_allocated(
        seed_workspace,
        active_item.id,
        -4,
    )

    await db_session.refresh(active_item)

    assert active_item.quantity_allocated == 6


@pytest.mark.asyncio
async def test_adjust_quantity_allocated_rejects_negative_result(
    db_session,
    seed_workspace,
    active_item,
):
    """Does not allow allocated quantity to become negative."""
    service = ItemService(db_session)

    with pytest.raises(InsufficientInventoryError):
        await service.adjust_quantity_allocated(
            seed_workspace,
            active_item.id,
            -1,
        )

    await db_session.refresh(active_item)
    assert active_item.quantity_allocated == 0


@pytest.mark.asyncio
async def test_adjust_quantity_allocated_zero_delta(
    db_session,
    seed_workspace,
    active_item,
):
    """A zero allocation adjustment does not change the quantity."""
    service = ItemService(db_session)

    await service.adjust_quantity_allocated(
        seed_workspace,
        active_item.id,
        0,
    )

    await db_session.refresh(active_item)

    assert active_item.quantity_allocated == 0


@pytest.mark.asyncio
async def test_adjust_quantity_allocated_zero_delta_does_not_fetch_item(
    db_session,
    seed_workspace,
):
    """A zero allocation adjustment returns without looking up the item."""
    service = ItemService(db_session)

    await service.adjust_quantity_allocated(
        seed_workspace,
        uuid.uuid4(),
        0,
    )


@pytest.mark.asyncio
async def test_adjust_quantity_allocated_item_not_found(
    db_session,
    seed_workspace,
):
    """A nonzero allocation adjustment for a missing item raises an error."""
    service = ItemService(db_session)

    with pytest.raises(ItemNotFoundError):
        await service.adjust_quantity_allocated(
            seed_workspace,
            uuid.uuid4(),
            1,
        )


@pytest.mark.asyncio
async def test_adjust_quantity_allocated_ignores_deleted_inventory(
    db_session,
    seed_workspace,
    active_item,
):
    """Soft-deleted inventory balances are not available for allocation."""
    service = ItemService(db_session)

    await create_bin_with_stock(
        db_session,
        seed_workspace,
        active_item.id,
        quantity=100,
        is_deleted=True,
    )

    with pytest.raises(InsufficientInventoryError):
        await service.adjust_quantity_allocated(
            seed_workspace,
            active_item.id,
            1,
        )

    await db_session.refresh(active_item)
    assert active_item.quantity_allocated == 0


@pytest.mark.asyncio
async def test_adjust_quantity_allocated_is_not_committed(
    db_session,
    seed_workspace,
    active_item,
):
    service = ItemService(db_session)
    item_id = active_item.id

    await create_bin_with_stock(
        db_session,
        seed_workspace,
        item_id,
        quantity=20,
    )

    await service.adjust_quantity_allocated(
        seed_workspace,
        item_id,
        10,
    )

    quantity = await db_session.scalar(
        select(Item.quantity_allocated).where(
            Item.id == item_id,
            Item.workspace_id == seed_workspace,
        )
    )
    assert quantity == 10

    await db_session.rollback()

    quantity = await db_session.scalar(
        select(Item.quantity_allocated).where(
            Item.id == item_id,
            Item.workspace_id == seed_workspace,
        )
    )
    assert quantity == 0
