import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

from erp.api.modules.bin.models import Bin
from erp.api.modules.inventory.models import Inventory
from erp.api.modules.item.models import Item

# ==============================================================================
# ITEM MODEL CONSTRAINT & RELATIONSHIP TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_item_model_unique_sku_per_workspace(db_session, seed_workspace):
    """The database enforces unique SKUs within the same workspace."""
    item1 = Item(
        workspace_id=seed_workspace,
        sku="DUPLICATE-SKU",
        title="First Item",
        base_price=100,
    )
    db_session.add(item1)
    await db_session.commit()

    item2 = Item(
        workspace_id=seed_workspace,
        sku="DUPLICATE-SKU",
        title="Second Item",
        base_price=200,
    )
    db_session.add(item2)

    with pytest.raises(IntegrityError):
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_item_model_cross_workspace_sku_allowed(
    db_session,
    seed_workspace,
    alt_workspace,
):
    """The same SKU is allowed in different workspaces."""
    item1 = Item(
        workspace_id=seed_workspace,
        sku="SHARED-SKU",
        title="Tenant A Item",
        base_price=100,
    )
    item2 = Item(
        workspace_id=alt_workspace,
        sku="SHARED-SKU",
        title="Tenant B Item",
        base_price=100,
    )

    db_session.add_all([item1, item2])
    await db_session.commit()

    assert item1.id is not None
    assert item2.id is not None


@pytest.mark.asyncio
async def test_item_model_base_price_defaults_to_zero(
    db_session,
    seed_workspace,
):
    item = Item(
        workspace_id=seed_workspace,
        sku="DEFAULT-PRICE-SKU",
        title="Default Price Item",
    )

    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    assert item.base_price == 0


@pytest.mark.asyncio
async def test_item_model_base_price_not_nullable(
    db_session,
    seed_workspace,
):
    statement = insert(Item).values(
        workspace_id=seed_workspace,
        sku="NULL-PRICE-SKU",
        title="Null Price Item",
        base_price=None,
    )

    with pytest.raises(IntegrityError):
        await db_session.execute(statement)
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_item_model_inventory_cascade_delete(
    db_session,
    seed_workspace,
):
    """Hard-deleting an item cascades to its loaded inventory records."""
    from sqlalchemy.orm import selectinload

    from erp.api.modules.bin.models import Bin

    item = Item(
        workspace_id=seed_workspace,
        sku="CASCADE-SKU",
        title="Cascade Test Item",
        base_price=50,
    )
    db_session.add(item)
    await db_session.flush()

    bin_record = Bin(
        workspace_id=seed_workspace,
        code="CASCADE-BIN",
        zone="A",
    )
    db_session.add(bin_record)
    await db_session.flush()

    inventory = Inventory(
        workspace_id=seed_workspace,
        item_id=item.id,
        bin_id=bin_record.id,
        quantity_on_hand=10,
    )
    db_session.add(inventory)
    await db_session.commit()

    inventory_id = inventory.id
    item_id = item.id

    # Explicitly load the relationship because it uses lazy="noload".
    result = await db_session.execute(
        select(Item)
        .options(selectinload(Item.inventory_items))
        .where(Item.id == item_id)
        .execution_options(populate_existing=True)
    )
    item = result.scalar_one()

    assert len(item.inventory_items) == 1
    assert item.inventory_items[0].id == inventory_id

    await db_session.delete(item)
    await db_session.commit()

    result = await db_session.execute(select(Inventory).where(Inventory.id == inventory_id))

    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_item_model_inventory_relationship(
    db_session,
    seed_workspace,
):
    """An item can have inventory records in multiple bins."""
    item = Item(
        workspace_id=seed_workspace,
        sku="MULTI-BIN-SKU",
        title="Multi Bin Item",
        base_price=100,
    )
    bin_a = Bin(
        workspace_id=seed_workspace,
        code="MULTI-BIN-A",
        zone="A",
    )
    bin_b = Bin(
        workspace_id=seed_workspace,
        code="MULTI-BIN-B",
        zone="B",
    )

    db_session.add_all([item, bin_a, bin_b])
    await db_session.commit()

    db_session.add_all(
        [
            Inventory(
                workspace_id=seed_workspace,
                item_id=item.id,
                bin_id=bin_a.id,
                quantity_on_hand=5,
            ),
            Inventory(
                workspace_id=seed_workspace,
                item_id=item.id,
                bin_id=bin_b.id,
                quantity_on_hand=7,
            ),
        ]
    )
    await db_session.commit()

    result = await db_session.execute(
        select(func.sum(Inventory.quantity_on_hand)).where(
            Inventory.workspace_id == seed_workspace,
            Inventory.item_id == item.id,
            Inventory.is_deleted.is_(False),
        )
    )

    assert result.scalar_one() == 12
