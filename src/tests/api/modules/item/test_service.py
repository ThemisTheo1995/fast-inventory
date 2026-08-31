import uuid

import pytest

from src.erp.api.modules.inventory.models import Inventory
from src.erp.api.modules.item.exceptions import ItemExistsError, ItemNotFoundError
from src.erp.api.modules.item.schemas import ItemCreate, ItemUpdate
from src.erp.api.modules.item.service import ItemService

# ==============================================================================
# 1. CREATE & TENANT ISOLATION
# ==============================================================================


def test_create_item_success_and_initializes_inventory(db_session, seed_workspace):
    """Verifies item creation succeeds and automatically seeds an inventory record."""
    service = ItemService(db=db_session)
    create_data = ItemCreate(title="New Widget", sku="WIDGET-001", base_price=5000)

    item = service.create_item(workspace_id=seed_workspace, data=create_data)

    assert item.id is not None
    assert item.workspace_id == seed_workspace
    assert item.title == "New Widget"
    assert item.sku == "WIDGET-001"

    # Verify inventory was initialized atomically
    inventory = db_session.query(Inventory).filter(Inventory.item_id == item.id).first()
    assert inventory is not None
    assert inventory.quantity_on_hand == 0


def test_create_item_duplicate_sku_fails(db_session, seed_workspace, active_item):
    """Verifies creating an item with an existing SKU in the same workspace throws an error."""
    service = ItemService(db=db_session)
    create_data = ItemCreate(title="Duplicate Widget", sku=active_item.sku, base_price=100)

    with pytest.raises(ItemExistsError):
        service.create_item(workspace_id=seed_workspace, data=create_data)


def test_create_item_cross_tenant_sku_allowed(db_session, seed_workspace, alt_workspace, active_item):  # noqa
    """Verifies the same SKU can be used across two different workspaces."""
    service = ItemService(db=db_session)
    # active_item is in seed_workspace, create the same SKU in alt_workspace
    create_data = ItemCreate(title="Alt Tenant Widget", sku=active_item.sku, base_price=100)

    cross_tenant_item = service.create_item(workspace_id=alt_workspace, data=create_data)

    assert cross_tenant_item.workspace_id == alt_workspace
    assert cross_tenant_item.sku == active_item.sku


# ==============================================================================
# 2. READ, PAGINATION & SEARCH
# ==============================================================================


def test_get_item_by_id_success(db_session, seed_workspace, active_item):
    """Verifies fetching a single item record."""
    service = ItemService(db=db_session)

    fetched = service.get_item(workspace_id=seed_workspace, item_id=active_item.id)
    assert fetched.id == active_item.id
    assert fetched.sku == active_item.sku


def test_get_item_not_found_raises(db_session, seed_workspace):
    """Verifies requesting a missing item ID throws a clean domain exception."""
    service = ItemService(db=db_session)

    with pytest.raises(ItemNotFoundError):
        service.get_item(workspace_id=seed_workspace, item_id=uuid.uuid4())


def test_get_item_tenant_isolation_fails(db_session, alt_workspace, active_item):
    """CRITICAL: Verifies a user in Workspace B cannot look up an item from Workspace A."""
    service = ItemService(db=db_session)

    with pytest.raises(ItemNotFoundError):
        service.get_item(workspace_id=alt_workspace, item_id=active_item.id)


def test_get_items_pagination(db_session, seed_workspace):
    """Verifies listing and paginating items works correctly."""
    service = ItemService(db=db_session)

    service.create_item(seed_workspace, ItemCreate(title="Item A", sku="SKU-A", base_price=10))
    service.create_item(seed_workspace, ItemCreate(title="Item B", sku="SKU-B", base_price=20))
    service.create_item(seed_workspace, ItemCreate(title="Item C", sku="SKU-C", base_price=30))

    response = service.get_items(workspace_id=seed_workspace, page=1, limit=2)

    assert response.total == 3
    assert len(response.items) == 2


def test_get_items_search_filter(db_session, seed_workspace):
    """Verifies the search parameter filters items by title and SKU."""
    service = ItemService(db=db_session)

    service.create_item(seed_workspace, ItemCreate(title="Apple MacBook", sku="MAC-01", base_price=1000))
    service.create_item(seed_workspace, ItemCreate(title="Banana Phone", sku="BAN-01", base_price=200))
    service.create_item(seed_workspace, ItemCreate(title="Generic Laptop", sku="APPLE-LP", base_price=500))

    # Search by Title
    res_title = service.get_items(workspace_id=seed_workspace, search="Banana")
    assert res_title.total == 1
    assert res_title.items[0].sku == "BAN-01"

    # Search matches both Title ("Apple MacBook") and SKU ("APPLE-LP")
    res_multi = service.get_items(workspace_id=seed_workspace, search="apple")
    assert res_multi.total == 2


# ==============================================================================
# 3. UPDATE & DELETE
# ==============================================================================


def test_update_item_metadata_success(db_session, seed_workspace, active_item):
    """Verifies basic fields update correctly."""
    service = ItemService(db=db_session)
    update_data = ItemUpdate(title="Updated Title", sku=active_item.sku, base_price=9999)

    updated = service.update_item(workspace_id=seed_workspace, item_id=active_item.id, data=update_data)

    assert updated.title == "Updated Title"
    assert updated.base_price == 9999
    assert updated.sku == active_item.sku


def test_update_item_duplicate_sku_fails(db_session, seed_workspace, active_item):
    """Verifies updating an item to a SKU already owned by another item fails."""
    service = ItemService(db=db_session)

    second_item = service.create_item(
        workspace_id=seed_workspace, data=ItemCreate(title="Second Item", sku="SKU-SECOND", base_price=10)
    )

    update_data = ItemUpdate(title=second_item.title, sku=active_item.sku, base_price=10)

    with pytest.raises(ItemExistsError):
        service.update_item(workspace_id=seed_workspace, item_id=second_item.id, data=update_data)


def test_update_item_same_sku_allowed(db_session, seed_workspace, active_item):
    """Verifies updating an item without changing its SKU does not trigger uniqueness errors."""
    service = ItemService(db=db_session)

    update_data = ItemUpdate(title="New Name", sku=active_item.sku, base_price=active_item.base_price)

    updated = service.update_item(workspace_id=seed_workspace, item_id=active_item.id, data=update_data)

    assert updated.title == "New Name"
    assert updated.sku == active_item.sku


def test_delete_item_success(db_session, seed_workspace, active_item):
    """Verifies an item is correctly soft-deleted."""
    service = ItemService(db=db_session)

    service.delete_item(workspace_id=seed_workspace, item_id=active_item.id)

    with pytest.raises(ItemNotFoundError):
        service.get_item(workspace_id=seed_workspace, item_id=active_item.id)


def test_delete_item_not_found(db_session, seed_workspace):
    """Verifies deleting a missing item raises an error."""
    service = ItemService(db=db_session)

    with pytest.raises(ItemNotFoundError):
        service.delete_item(workspace_id=seed_workspace, item_id=uuid.uuid4())
