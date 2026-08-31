import pytest
from sqlalchemy.exc import IntegrityError

from src.erp.api.modules.inventory.models import Inventory
from src.erp.api.modules.item.models import Item

# ==============================================================================
# Model Constraint & Relationship Tests
# ==============================================================================


def test_item_model_unique_sku_per_workspace(db_session, seed_workspace):
    """Verifies that the database enforces unique SKUs within the same workspace."""
    item1 = Item(workspace_id=seed_workspace, sku="DUPLICATE-SKU", title="First Item", base_price=100)
    db_session.add(item1)
    db_session.commit()

    item2 = Item(
        workspace_id=seed_workspace,
        sku="DUPLICATE-SKU",  # Same SKU
        title="Second Item",
        base_price=200,
    )
    db_session.add(item2)

    with pytest.raises(IntegrityError):
        db_session.commit()

    # Rollback the failed transaction so it doesn't break teardown
    db_session.rollback()


def test_item_model_cross_workspace_sku_allowed(db_session, seed_workspace, alt_workspace):
    """Verifies that the unique constraint allows the same SKU in different workspaces."""
    item1 = Item(workspace_id=seed_workspace, sku="SHARED-SKU", title="Tenant A Item", base_price=100)
    item2 = Item(
        workspace_id=alt_workspace,
        sku="SHARED-SKU",  # Same SKU, different workspace
        title="Tenant B Item",
        base_price=100,
    )

    db_session.add_all([item1, item2])
    db_session.commit()  # Should succeed without IntegrityError

    assert item1.id is not None
    assert item2.id is not None


def test_item_model_base_price_nullable(db_session, seed_workspace):
    """Verifies that base_price can be explicitly set to None."""
    item = Item(workspace_id=seed_workspace, sku="NULL-PRICE-SKU", title="Free or Undecided Item", base_price=None)
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    assert item.base_price is None


def test_item_model_inventory_cascade_delete(db_session, seed_workspace):
    """Verifies that hard-deleting an Item cascades and deletes its linked Inventory record."""
    item = Item(workspace_id=seed_workspace, sku="CASCADE-SKU", title="Cascade Test Item", base_price=50)
    db_session.add(item)
    db_session.commit()

    inventory = Inventory(
        workspace_id=seed_workspace, item_id=item.id, quantity_on_hand=10, quantity_allocated=0, quantity_on_order=0
    )
    db_session.add(inventory)
    db_session.commit()

    # Verify inventory exists
    inv_id = inventory.id
    assert db_session.query(Inventory).filter_by(id=inv_id).first() is not None

    # Hard delete the item (bypassing soft-delete to test SQLAlchemy cascade)
    db_session.delete(item)
    db_session.commit()

    # Verify the associated inventory was automatically deleted via 'delete-orphan' cascade
    assert db_session.query(Inventory).filter_by(id=inv_id).first() is None
