import uuid

import pytest

from erp.api.modules.supplier.exceptions import (
    SupplierEmailExistsError,
    SupplierNotFoundError,
)
from erp.api.modules.supplier.models import Supplier
from erp.api.modules.supplier.schemas import SupplierCreate, SupplierUpdate
from erp.api.modules.supplier.service import SupplierService

# ==============================================================================
# EXISTING TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_service_create_supplier(db_session, seed_workspace):
    """Verifies the service layer correctly persists a supplier tied to a workspace."""
    service = SupplierService(db=db_session)
    create_data = SupplierCreate(name="Tech Components Ltd", email="marcus@techcomp.io")

    supplier = await service.create_supplier(workspace_id=seed_workspace, data=create_data)

    assert supplier.id is not None
    assert supplier.workspace_id == seed_workspace
    assert supplier.name == "Tech Components Ltd"

    # Verify it's actually committed to the DB
    db_record = await db_session.get(Supplier, supplier.id)
    assert db_record is not None


@pytest.mark.asyncio
async def test_service_get_supplier_by_id(db_session, seed_workspace, active_supplier):
    """Verifies fetching a single supplier record scoped by tenant workspace."""
    service = SupplierService(db=db_session)

    fetched = await service.get_supplier(workspace_id=seed_workspace, supplier_id=active_supplier.id)
    assert fetched.id == active_supplier.id
    assert fetched.name == active_supplier.name


@pytest.mark.asyncio
async def test_service_get_supplier_not_found_raises(db_session, seed_workspace):
    """Verifies that requesting a missing supplier ID throws a clean domain exception."""
    service = SupplierService(db=db_session)
    random_id = uuid.uuid4()

    with pytest.raises(SupplierNotFoundError):
        await service.get_supplier(workspace_id=seed_workspace, supplier_id=random_id)


@pytest.mark.asyncio
async def test_service_get_supplier_isolation_protection(db_session, alt_workspace, active_supplier):
    """
    CRITICAL SERVICE CHECK: Verifies that a user in Workspace B cannot look up
    a supplier belonging to Workspace A via the service layer.
    """
    service = SupplierService(db=db_session)

    # Accessing Workspace A's active_supplier using alt_workspace (Workspace B)
    with pytest.raises(SupplierNotFoundError):
        await service.get_supplier(workspace_id=alt_workspace, supplier_id=active_supplier.id)


@pytest.mark.asyncio
async def test_service_update_supplier(db_session, seed_workspace, active_supplier):
    """Verifies target field mutations apply cleanly via service models."""
    service = SupplierService(db=db_session)
    update_data = SupplierUpdate(name="Global Logistics Logistics Ltd")

    updated = await service.update_supplier(
        workspace_id=seed_workspace, supplier_id=active_supplier.id, data=update_data
    )
    assert updated.name == "Global Logistics Logistics Ltd"
    assert updated.email == active_supplier.email  # Kept unchanged


@pytest.mark.asyncio
async def test_service_delete_supplier(db_session, seed_workspace, active_supplier):
    """Verifies that the service completely removes or soft-deletes a record."""
    service = SupplierService(db=db_session)

    await service.delete_supplier(workspace_id=seed_workspace, supplier_id=active_supplier.id)

    with pytest.raises(SupplierNotFoundError):
        await service.get_supplier(workspace_id=seed_workspace, supplier_id=active_supplier.id)


# ==============================================================================
# NEW TESTS (Pagination, Search, Uniqueness, Soft-Delete Restoration)
# ==============================================================================


@pytest.mark.asyncio
async def test_service_create_supplier_email_exists_raises(db_session, seed_workspace, active_supplier):
    """Verifies creating a supplier with an already active email throws an error."""
    service = SupplierService(db=db_session)
    create_data = SupplierCreate(name="Imposter Ltd", email=active_supplier.email)

    with pytest.raises(SupplierEmailExistsError):
        await service.create_supplier(workspace_id=seed_workspace, data=create_data)


@pytest.mark.asyncio
async def test_service_create_supplier_restores_soft_deleted(db_session, seed_workspace, active_supplier):
    """Verifies that creating a supplier with a soft-deleted email restores the original record."""
    service = SupplierService(db=db_session)
    original_id = active_supplier.id

    # 1. Soft-delete the active supplier
    await service.delete_supplier(workspace_id=seed_workspace, supplier_id=original_id)

    # 2. Re-create a supplier with the same email but different name
    create_data = SupplierCreate(name="Rebranded Ltd", email=active_supplier.email)
    restored_supplier = await service.create_supplier(workspace_id=seed_workspace, data=create_data)

    # 3. Assertions to ensure it's the SAME record, now active, with updated info
    assert restored_supplier.id == original_id
    assert restored_supplier.name == "Rebranded Ltd"
    assert not restored_supplier.is_deleted


@pytest.mark.asyncio
async def test_service_update_supplier_email_exists_raises(db_session, seed_workspace, active_supplier):
    """Verifies that updating a supplier to an email already in use by another throws an error."""
    service = SupplierService(db=db_session)

    # Create a second supplier
    second_supplier = await service.create_supplier(
        workspace_id=seed_workspace, data=SupplierCreate(name="Second Supplier", email="second@test.com")
    )

    # Attempt to change the second supplier's email to the active_supplier's email
    update_data = SupplierUpdate(name=second_supplier.name, email=active_supplier.email)

    with pytest.raises(SupplierEmailExistsError):
        await service.update_supplier(workspace_id=seed_workspace, supplier_id=second_supplier.id, data=update_data)


@pytest.mark.asyncio
async def test_service_update_supplier_remove_email(db_session, seed_workspace, active_supplier):
    """Verifies that removing a supplier's email (setting to None) bypasses uniqueness checks."""
    service = SupplierService(db=db_session)
    assert active_supplier.email is not None

    update_data = SupplierUpdate(name=active_supplier.name, email=None)

    updated = await service.update_supplier(
        workspace_id=seed_workspace, supplier_id=active_supplier.id, data=update_data
    )

    assert updated.email is None
    assert updated.name == active_supplier.name


@pytest.mark.asyncio
async def test_service_update_supplier_same_email_allowed(db_session, seed_workspace, active_supplier):
    """Verifies that updating a supplier with its own current email doesn't trigger a unique constraint error."""
    service = SupplierService(db=db_session)

    # Updating name, but keeping the email the exact same
    update_data = SupplierUpdate(name="Same Email Ltd", email=active_supplier.email)

    updated = await service.update_supplier(
        workspace_id=seed_workspace, supplier_id=active_supplier.id, data=update_data
    )

    assert updated.name == "Same Email Ltd"
    assert updated.email == active_supplier.email


@pytest.mark.asyncio
async def test_service_get_suppliers_pagination(db_session, seed_workspace, active_supplier):  # noqa
    """Verifies listing and paginating suppliers works correctly."""
    service = SupplierService(db=db_session)

    # Create a few extra suppliers (active_supplier is already 1)
    await service.create_supplier(seed_workspace, SupplierCreate(name="Supplier A", email="a@test.com"))
    await service.create_supplier(seed_workspace, SupplierCreate(name="Supplier B", email="b@test.com"))
    await service.create_supplier(seed_workspace, SupplierCreate(name="Supplier C", email="c@test.com"))

    # Total should be 4. Let's fetch page 1, limit 2
    response = await service.get_suppliers(workspace_id=seed_workspace, page=1, limit=2)

    assert response.total == 4
    assert len(response.items) == 2


@pytest.mark.asyncio
async def test_service_get_suppliers_search(db_session, seed_workspace):
    """Verifies the search parameter filters suppliers by name and email."""
    service = SupplierService(db=db_session)

    await service.create_supplier(seed_workspace, SupplierCreate(name="Apple Supply", email="contact@apple.com"))
    await service.create_supplier(seed_workspace, SupplierCreate(name="Banana Ltd", email="hello@bananas.com"))
    await service.create_supplier(seed_workspace, SupplierCreate(name="Cherry Inc", email="apple@cherry.com"))

    # Search by Name
    res_name = await service.get_suppliers(workspace_id=seed_workspace, search="Banana")
    assert res_name.total == 1
    assert res_name.items[0].name == "Banana Ltd"

    # Search by Email or Name overlap (Apple should match "Apple Supply" by name, and "Cherry Inc" by email)
    res_multi = await service.get_suppliers(workspace_id=seed_workspace, search="apple")
    assert res_multi.total == 2

    # Search should be case-insensitive
    res_case = await service.get_suppliers(workspace_id=seed_workspace, search="CHERRY")
    assert res_case.total == 1
    assert res_case.items[0].name == "Cherry Inc"
