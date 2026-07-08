import uuid

import pytest

from src.erp.api.modules.supplier.exceptions import SupplierNotFoundError
from src.erp.api.modules.supplier.models import Supplier
from src.erp.api.modules.supplier.schemas import SupplierCreate, SupplierUpdate
from src.erp.api.modules.supplier.service import SupplierService


def test_service_create_supplier(db_session, seed_workspace):
    """Verifies the service layer correctly persists a supplier tied to a workspace."""
    service = SupplierService(db=db_session)
    create_data = SupplierCreate(name="Tech Components Ltd", email="marcus@techcomp.io")

    supplier = service.create_supplier(workspace_id=seed_workspace, data=create_data)

    assert supplier.id is not None
    assert supplier.workspace_id == seed_workspace
    assert supplier.name == "Tech Components Ltd"

    # Verify it's actually committed to the DB
    db_record = db_session.query(Supplier).filter(Supplier.id == supplier.id).first()
    assert db_record is not None


def test_service_get_supplier_by_id(db_session, seed_workspace, active_supplier):
    """Verifies fetching a single supplier record scoped by tenant workspace."""
    service = SupplierService(db=db_session)

    fetched = service.get_supplier(workspace_id=seed_workspace, supplier_id=active_supplier.id)
    assert fetched.id == active_supplier.id
    assert fetched.name == active_supplier.name


def test_service_get_supplier_not_found_raises(db_session, seed_workspace):
    """Verifies that requesting a missing supplier ID throws a clean domain exception."""
    service = SupplierService(db=db_session)
    random_id = uuid.uuid4()

    with pytest.raises(SupplierNotFoundError):
        service.get_supplier(workspace_id=seed_workspace, supplier_id=random_id)


def test_service_get_supplier_isolation_protection(db_session, alt_workspace, active_supplier):
    """
    CRITICAL SERVICE CHECK: Verifies that a user in Workspace B cannot look up
    a supplier belonging to Workspace A via the service layer.
    """
    service = SupplierService(db=db_session)

    # Accessing Workspace A's active_supplier using alt_workspace (Workspace B)
    with pytest.raises(SupplierNotFoundError):
        service.get_supplier(workspace_id=alt_workspace, supplier_id=active_supplier.id)


def test_service_update_supplier(db_session, seed_workspace, active_supplier):
    """Verifies target field mutations apply cleanly via service models."""
    service = SupplierService(db=db_session)
    update_data = SupplierUpdate(name="Global Logistics Logistics Ltd")

    updated = service.update_supplier(workspace_id=seed_workspace, supplier_id=active_supplier.id, data=update_data)
    assert updated.name == "Global Logistics Logistics Ltd"
    assert updated.email == active_supplier.email  # Kept unchanged


def test_service_delete_supplier(db_session, seed_workspace, active_supplier):
    """Verifies that the service completely removes or soft-deletes a record."""
    service = SupplierService(db=db_session)

    service.delete_supplier(workspace_id=seed_workspace, supplier_id=active_supplier.id)

    with pytest.raises(SupplierNotFoundError):
        service.get_supplier(workspace_id=seed_workspace, supplier_id=active_supplier.id)
